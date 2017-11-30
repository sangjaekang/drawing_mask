# -*- coding:utf-8 -*-
from tkinter import *
from PIL import Image
from PIL import ImageTk
from tkinter import filedialog
import cv2

import numpy as np
import pandas as pd

import os
import re
import csv

### DEFAULT SETTING 상수
# 표기에 쓰이는 색상
COLOR_PALETTE = [(255,255,255),
                (0,0,150),
                (0,150,0),
                (150,0,150),
                (100,50,100),
                (50,100,50),
                (100,100,100),
                ]


# 표기 기능 종류
TYPE_OPTION = ["bounding box", "painting contour line"]

# output 저장 위치
TEMP_DIR = "temp" # 임시 작업공간
MASK_IMG_DIR = 'bounding_box' # boundary box 저장 공간
CONTOUR_IMG_DIR = 'contour' # Contour Area 저장 공간

# 프로그램 상단에 뜰 제목
APPLICATION_TITLE = "MEDI-DRAW"

class Application(Frame):
    def __init__(self,master):
        global TYPE_OPTION, BACKGROUND_COLOR
        # Create a container
        self.master = master

        self.image_dir_path = None # input directory의 위치
        self.bbox_img_dir = None # mask image가 저장되는 위치
        self.contour_img_dir = None # contour image가 저장되는 위치
        self.temp_path = None # points들의 정보가 저장되는 위치 (작업 공간)

        self.input_image_list = None # input directory의 image list
        self.image_index = None # 현재 보여주는 image index
        self.image_on_canvas = None # 현재 canvas에서 보여주는 image
        self.cv_image = None # 현재 canvas에서 보여주는 opencv image
        self.annotation_type = TYPE_OPTION[0] # 어떻게 표시할 것인지 결정
        self.canvas = None # image가 담기는 canvas

        ## bounding box variable (Detection & annotation)
        self.bbox_df = None # bounding box의 좌표와 속성을 저장하는 Dataframe
        self.bbox_type = 1 # bounding box의 종류 (annotation의 종류를 나누기 위함)
        self.bbox_color = 'green' # bounding box의 색상
        self.bbox_masks_dict = {} # bounding box의 mask
        self.bbox_changed = False # bbounding box의 내용이 바뀌었는지 check하는 인자

        ## contours variable (Segmentation & Contour)
        self.contour = None
        self.contour_points = None
        self.contour_order_stack = [] # contour의 order를 저장한 Stack
        self.contour_point_dicts = {} # contour의 point를 저장한 dictionarys key : Type , value : contour point list
        self.contour_type = 1
        self.contour_color = 'green'
        self.contour_masks_dict = {}
        self.contour_changed = False

        ## configuration variable
        self.line_thickness = 1 # 선 굵기
        self.blend_ratio = 0.2 # 색 결합 시 비율
        self.brightness_gamma = 1 # 이미지의 명도 보정(Gamma Correction)
        self.redfree_or_not = False
        self.clahe_value = 0 # clahe 적용 시, Tile size

        self.set_annotation_window() # 화면의 요소(canvas,button,textbox etc)들을 생성
        self.bind_key_to_frame()

    ### UI 화면 및 키 구성
    '''
    1. set_annotation_window : UI 화면 요소
        - 이미지 Canvas 창
        - 조작 Frame 창
            - 설정 및 출력 창
                - 디렉토리 설정 버튼
                - 표기 방식 설정 버튼
                - 파일이름 출력 창
                - 파일 이동 스크롤바
                - 디버거 창
                - 원본 이미지 창
            - 화면 설정 창
                - 선 굵기 설정
                - 마스크 투명도 설정
                - 명도 조절
                - CLAHE 조절
                - RED-FREE 설정

    2. bind_key_to_canvas : CANVAS 내 UI 조작 구성
        - 공통
            - move_prev_image & move_next_image : 파일 변경(변경 내용이 있으면 자동 저장)
            - reset_canvas : 작업 내역 리셋 (초기 load된 이미지로 돌아감)
            - set_color_type : 색 변경
            - save_annotation_mask : 작업 내역 저장

        - boundary box
            - press_bbox : Bounding box 시작
            - drag_bbox  : Bounding box 늘리고 줄이기
            - drop_bbox : Bounding box 결정
            - cancel_bbox_mask :이전 Bounding box 취소

        - contour area
            점끼리 자동으로 Smooth하게 선이 이어짐, 선이 이어지고 나서, fill_in_contour하면
            그 안이 채워지는 구조
            - press_contour : Contour 점 찍기
            - drag_contour : Contour 연속 점 찍기
            - drop_contour :
            - fill_in_contour : contour 내부 색 채우기
            - cancel_contour_mask : 이전 contour 취소

    3. bind_key_to_frame : Frame 내 UI 조작 구성
        - select_input_directory : 우리가 annotating할 이미지가 담긴 디렉토리 설정
        - set_annotation_type : annotation type(color) 설정
        - jump_to_image : File Scroll바 조작 시 움직임
        - set_line_thickness : Line의 두께 설정
        - set_blend_ratio : 마스크의 투명도 설정
        - set_brightness : 이미지의 명도 설정
        - set_clahe : 이미지의 대조 설정
        - set_redfree : 이미지를 red free 이미지르 변경
    '''
    ##
    def set_annotation_window(self):
        global TYPE_OPTION, APPLICATION_TITLE
        self.master.title(APPLICATION_TITLE)

        ## 이미지 canvas 창 구성
        self.canvas=Canvas(self.master, width=1010, height=1010, background='white')
        self.canvas.grid(row=0,column=0)
        # Button & Text 창 구성
        self.frame = Frame(self.master,width=100,height=500)
        self.frame.grid(row=0,column=1, sticky="ne")
        ## 디렉토리 Button 구성
        row_idx = 0
        directory_label=Label(self.frame, text="작업할 이미지 디렉토리 :",height=2).grid(row=row_idx,column=0,pady=2,sticky='w')
        self.directory_btn = Button(self.frame, text="input image directory",width=30,height=2)
        self.directory_btn.grid(row=row_idx,column=0,columnspan=2,sticky="nwe",pady=5)
        ## Annotation Button 구성
        row_idx +=1
        Label(self.frame,text="표시 방법 : ",height=2).grid(row=row_idx,column=0,pady=2,sticky='w')
        self.type_label = StringVar()
        self.type_label.set(TYPE_OPTION[0])
        self.annotation_menu = OptionMenu(self.frame, self.type_label, *TYPE_OPTION,command=self.set_annotation_type)
        self.annotation_menu.grid(row=row_idx,column=1,sticky="e",pady=5)

        ## Filename show 구성
        row_idx+=1
        self.filename_text = StringVar()
        Label(self.frame, text="현재 파일 : ").grid(row=row_idx,column=0, sticky="w")
        Label(self.frame,textvariable=self.filename_text).grid(row = row_idx,column = 1,sticky = "ew")
        row_idx+=1
        ## file moving scale
        self.file_scale = Scale(self.frame, from_=0,to=0, orient=HORIZONTAL, resolution=1)
        self.file_scale.set(0)
        self.file_scale.grid(row=row_idx,column=0,columnspan=2,sticky="ew")
        ## Debug window 구성
        row_idx+=1
        self.debugbox = Text(self.frame,height=7,width=30)
        self.debugbox.grid(row=row_idx,column=0,columnspan=2,sticky="ew",pady=5)
        row_idx+=1
        self.preview_imagebox = Label(self.frame,height=15,width=30,background='black')
        self.preview_imagebox.grid(row=row_idx,column=0,columnspan=2,sticky="ew",pady=5)
        ## Configuration 구성
        ### 선 굵기 결정
        row_idx+=1
        Label(self.frame, text = "선 굵기[bounding box mode] :\n클수록 선의 굵기가 굵어짐",justify=LEFT)\
        .grid(row=row_idx,column=0, sticky="w",pady=5)
        row_idx+=1
        self.line_thickness_scale = Scale(self.frame, from_=1,to=5, orient=HORIZONTAL)
        self.line_thickness_scale.set(2)
        self.line_thickness_scale.grid(row=row_idx,column=0,columnspan=2,sticky="ew")
        ### 블렌딩 비율 결정
        row_idx+=1
        Label(self.frame, text = "Blending 비율[drawing mode] :\n클수록 Segmentation 색이 진해짐",justify=LEFT)\
        .grid(row=row_idx,column=0, sticky="w",pady=5)
        row_idx+=1
        self.blend_scale = Scale(self.frame, from_=0,to=1, orient=HORIZONTAL,resolution=0.05)
        self.blend_scale.set(0.5)
        self.blend_scale.grid(row=row_idx,column=0,columnspan=2,sticky="ew")
        ### 명도 결정
        row_idx+=1
        Label(self.frame, text = "명도 변경[Gamma Correction] :\n작을수록 어두워짐, 클수록 밝아짐",justify=LEFT)\
        .grid(row=row_idx,column=0, sticky="w",pady=5)
        row_idx+=1
        self.brightness_scale = Scale(self.frame, from_=0.1,to=2, orient=HORIZONTAL,resolution=0.05)
        self.brightness_scale.set(1)
        self.brightness_scale.grid(row=row_idx,column=0,columnspan=2,sticky="ew")
        ### CLAHE 적용
        row_idx+=1
        Label(self.frame, text = "대조 강조[CLAHE Algorithm 이용] :\n0은 적용 안됨, 2~20은 적용 상수",justify=LEFT)\
        .grid(row=row_idx,column=0, sticky="w",pady=5)
        row_idx+=1
        self.clahe_scale = Scale(self.frame, from_=0,to=20, orient=HORIZONTAL,resolution=2)
        self.clahe_scale.set(0)
        self.clahe_scale.grid(row=row_idx,column=0,columnspan=2,sticky="ew")
        ### RED FREE 이미지로 변환
        row_idx+=1
        Label(self.frame, text = "Red-Free image로의 변환 유무 :",justify=LEFT).grid(row=row_idx, column=0, sticky="w",pady=5)
        self.check_rf = IntVar()
        self.rf_button = Checkbutton(self.frame, text='Red-Free', variable=self.check_rf)
        self.rf_button.grid(row=row_idx, column=1, sticky="w", pady=5)
        self.master.minsize(width=1100,height=1010)


    def bind_key_to_canvas(self):
        global TYPE_OPTION
        self.master.bind("<Left>",self.move_prev_image)
        self.master.bind("<Right>",self.move_next_image)
        self.master.bind("<Escape>",self.save_annotation_mask)
        self.master.bind("<Control-s>",self.save_annotation_mask)
        self.master.bind("<Control-r>",self.reset_canvas)
        self.master.bind("<Key>",self.set_color_type)

        if self.annotation_type  == TYPE_OPTION[0]:
            # Bounding Box에 관련된 것으로 Binding
            self.canvas.bind("<Button-1>", self.press_bbox)
            self.canvas.bind("<B1-Motion>", self.drag_bbox)
            self.canvas.bind("<ButtonRelease-1>", self.drop_bbox)
            self.master.bind("<Control-x>",self.cancel_bbox_mask)

        elif self.annotation_type  == TYPE_OPTION[1]:
            # Drawing Contour에 관련된 것으로 Binding
            self.canvas.bind("<Button-1>", self.press_contour)
            self.canvas.bind("<B1-Motion>", self.drag_contour)
            self.canvas.bind("<ButtonRelease-1>", self.drop_contour)
            self.master.bind("<Control-x>",self.cancel_contour_mask)
            self.master.bind("<Control-f>",self.fill_in_contour)

    def bind_key_to_frame(self):
        # UI 요소와 기능을 분리시켜 놓으면 유지보수할 때 좋아짐
        # But Tkinter의 한계로 인해, Optionmenu는 분리시키지 못함
        self.directory_btn.configure(command=self.select_input_directory)
        #self.annotation_menu.configure(command=self.set_annotation_type) : command와 Optionmenu와의 Dynamic Binding이 되지 않음.
        self.file_scale.configure(command=self.jump_to_image)
        self.line_thickness_scale.configure(command=self.set_line_thickness)
        self.blend_scale.configure(command=self.set_blend_ratio)
        self.brightness_scale.configure(command=self.set_brightness)
        self.clahe_scale.configure(command=self.set_clahe)
        self.rf_button.configure(command=self.set_redfree)

    ### UI Showing 구성
    '''
    1. 이미지 관련
        - show_canvas_image : 화면 내 Canvas(작업 공간) 내에 올려질 Image를 보여주는 메소드
        - show_preview_image : 화면 내 preview box에 올려진 Image를 보여주는 메소드
        - show_annotation_mask : Canvas 위에 User가 그린 annotation을 보여주는 메소드
            - show_bbox_mask    : Annotation 중 Boundary box를 보여주는 메소드
            - show_contour_mask : Annotation 중 Contour Area를 보여주는 메소드
    2. 파일이름 관련
        - show_filename_text : 화면 내 파일이름을 보여주는 메소드
    3. 디버거 관련
        - append_text_debugbox : 화면 내 debugbox에 글자를 추가하는 메소드
        - clear_debugbox : 화면 내 debugbox 안 내용을 다 지우는 메소드
    '''
    def show_preview_image(self):
        # 현재 cv_image의 original image를 보여줌
        if self.cv_image is not None:
            preview_image = cv2.resize(self.cv_image,(300,300))
            self.preview_image = ImageTk.PhotoImage(Image.fromarray(preview_image))
            self.preview_imagebox.configure(image=self.preview_image,height=300,width=30)
            self.preview_imagebox.image = self.preview_image


    def show_canvas_image(self):
        # 현재 image index의 image를 보여줌
        if self.input_image_list is None:
            return
        filename = self.input_image_list[self.image_index]
        path = os.path.join(self.image_dir_path,filename)
        if len(path) > 0:
            image = cv2.imread(path)
            self.cv_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            adjusted_cv_image = self.adjust_image()
            # convert the images to PIL format and then to ImageTk format
            self.image = ImageTk.PhotoImage(Image.fromarray(adjusted_cv_image))

            if self.image_on_canvas is None:
                # if the Canvas are None, initialize them
                self.image_on_canvas = self.canvas.create_image(0,0,anchor="nw",image=self.image)
            else:
                self.canvas.itemconfig(self.image_on_canvas, image=self.image)


    def show_annotation_mask(self):
        if self.annotation_type ==TYPE_OPTION[0]:
            self.show_bbox_mask()
        elif self.annotation_type ==TYPE_OPTION[1]:
            self.show_contour_mask()
        else:
            self.show_bbox_mask()


    def show_bbox_mask(self):
        global COLOR_PALETTE
        if self.cv_image is None:
            return

        image_bg = self.adjust_image()

        if len(self.bbox_masks_dict) == 0 :
            return

        for bbox_type, bbox_mask in self.bbox_masks_dict.items():
            bbox_color = np.array(COLOR_PALETTE[bbox_type],dtype=np.uint8) # the numpy of color
            bbox_mask_inv = cv2.bitwise_not(bbox_mask)

            # Boolean mask image를 Color를 입힌 RGB image로 바꾸어줌
            bbox_mask_fg = np.outer(bbox_mask,bbox_color).reshape(bbox_mask.shape[0],-1,len(bbox_color))
            image_bg = cv2.bitwise_and(image_bg,image_bg,mask=bbox_mask_inv)
            image_bg = cv2.add(bbox_mask_fg, image_bg)

        self.image = ImageTk.PhotoImage(Image.fromarray(image_bg))
        self.canvas.itemconfig(self.image_on_canvas, image=self.image)


    def show_contour_mask(self):
        if self.cv_image is None:
            return
        image_bg = self.adjust_image()

        for contour_type, contour_mask in self.contour_masks_dict.items():
            fill_color = np.array(COLOR_PALETTE[contour_type],dtype=np.uint8) # the numpy of color
            contour_mask_inv = cv2.bitwise_not(contour_mask)

            # Boolean mask image를 Color를 입힌 RGB image로 바꾸어줌
            contour_mask_fg = np.outer(contour_mask,fill_color).reshape(contour_mask.shape[0],-1,len(fill_color))
            contour_mask_fg = np.uint8(self.blend_ratio*contour_mask_fg)
            image_bg = cv2.add(contour_mask_fg, image_bg)

        self.image = ImageTk.PhotoImage(Image.fromarray(image_bg))
        self.canvas.itemconfig(self.image_on_canvas, image=self.image)


    def show_filename_text(self):
        filename = self.input_image_list[self.image_index]
        filename = filename + "   ... ( {} / {} )".format(self.image_index+1,len(self.input_image_list))
        self.filename_text.set(filename)


    def append_text_debugbox(self,text):
        if isinstance(text,str):
            self.debugbox.insert(END,text + "\n")


    def clear_debugbox(self):
        self.debugbox.delete(1.0,END)

    ### 파일 저장 및 불러오기
    '''
    파일 저장
        - save_annotation_mask
            - save_bbox_mask
                - save_bbox_mask_by_csv : bounding box의 좌표값을 dataframe형태로 한 후, csv format으로 저장
                - save_bbox_mask_by_image : bounding box 안을 채워, png format으로 저장
            - save_contour_mask
                - save_contour_mask_by_npz : contour의 좌표값 리스트는 현재
                                             dict(annotation type별 contour 집합) - list(같은 annotation type의 contour 집합) - np.array(하나의 contour)
                                             로 구조화되어 구성되어 있음.
                                             이 구조 그대로 npz format으로 저장
                - save_contour_mask_by_image : contour area를 png format으로 저장
    파일 불러오기
        - load_annotation_mask
            - load_bbox_mask : temp 폴더 내의 bounding box dataframe을 불러옴.
            - load_contour_mask : temp 폴더 내의 contour의 구조체를 불러옴.
        복원
            - set_bbox_mask : 현재 저장된 annotation 정보에 따라 해당 annotation type의 bounding box 이미지 복원
            - set_contour_mask : 현재 저장된 annotation 정보에 따라 해당 annotation type의 contour mask 이미지 복원
    작업 내용 초기화
        - init_annotation_mask : 저장및 불러오는 작업 시 혼선을 줄이기 위해, 작업 내역을 초기화 하는 작업
    '''
    def save_annotation_mask(self,event=None):
        if self.bbox_changed:
            self.save_bbox_mask()
        if self.contour_changed:
            self.save_contour_mask()

    def save_bbox_mask(self,event=None):
        # bbox points dataframe를 csv파일 형태로 temp에 저장
        self.save_bbox_mask_by_csv()
        # bbox points dataframe을 이미지 형태로 mask에 저장
        self.save_bbox_mask_by_image()

    def save_contour_mask(self,event=None):
        self.save_contour_mask_by_npz()
        self.save_contour_mask_by_image()


    def save_bbox_mask_by_image(self):
        file_path = self.input_image_list[self.image_index]
        filename, ext = os.path.splitext(file_path)

        # 속이 채워진 bbox_img를 만들기 위함
        prev_ = self.line_thickness
        self.line_thickness = cv2.FILLED
        for bbox_type in self.bbox_masks_dict:
            self.set_bbox_mask(bbox_type,color=255)
        self.line_thickness = prev_

        for bbox_type, bbox_mask in self.bbox_masks_dict.items():
            bbox_type_dir = os.path.join(self.bbox_img_dir,str(bbox_type))
            if not os.path.exists(bbox_type_dir):
                os.makedirs(bbox_type_dir)
            output_path = os.path.join(bbox_type_dir,filename+".png")
            if np.sum(bbox_mask) == 0 :
                if os.path.exists(output_path):
                    self.append_text_debugbox("save empty bounding box(type : {})".format(bbox_type))
                    os.remove(output_path)
            else:
                cv2.imwrite(output_path,bbox_mask)
                self.append_text_debugbox("save bounding box(type : {}) by Image".format(bbox_type))


    def save_bbox_mask_by_csv(self):
        file_path = self.input_image_list[self.image_index]
        filename, ext = os.path.splitext(file_path)

        output_path = os.path.join(self.temp_path, filename + ".csv")
        if self.bbox_df is not None:
            if self.bbox_df.empty:
                if os.path.exists(output_path):
                    self.append_text_debugbox("empty bounding box mask")
                    os.remove(output_path)
            else:
                self.append_text_debugbox("save to {}".format(output_path))
                self.bbox_df.to_csv(output_path,index=False)


    def save_contour_mask_by_npz(self):
        file_path = self.input_image_list[self.image_index]
        filename, ext = os.path.splitext(file_path)

        output_path = os.path.join(self.temp_path, filename + ".npz")
        if len(self.contour_point_dicts) == 0 or len(self.contour_order_stack) == 0:
            if os.path.exists(output_path):
                self.append_text_debugbox("empty contour mask")
                os.remove(output_path)
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            np.savez(output_path, self.contour_point_dicts, self.contour_order_stack)
            self.append_text_debugbox("save to {}".format(output_path))


    def save_contour_mask_by_image(self):
        # 현재 그린 contour mask를 저장함
        file_path = self.input_image_list[self.image_index]
        filename, ext = os.path.splitext(file_path)

        # 속이 채워진 contour mask를 만들기 위함(255해야지 보인다)
        for contour_type in self.contour_masks_dict:
            self.set_contour_mask(contour_type,color=255)

        for contour_type, contour_mask in self.contour_masks_dict.items():
            contour_mask_dir = os.path.join(self.contour_img_dir,str(contour_type))
            if not os.path.exists(contour_mask_dir):
                os.makedirs(contour_mask_dir)
            output_path = os.path.join(contour_mask_dir,filename+".png")
            if np.sum(contour_mask) == 0 :
                if os.path.exists(output_path):
                    os.remove(output_path)
            else:
                cv2.imwrite(output_path,contour_mask)
                self.append_text_debugbox("save contour mask(type : {}) by Image".format(contour_type))


    def load_annotation_mask(self):
        if self.annotation_type == TYPE_OPTION[0]:
            self.load_bbox_mask()
        elif self.annotation_type == TYPE_OPTION[1]:
            self.load_contour_mask()
        else:
            self.load_bbox_mask()


    def load_bbox_mask(self):
        file_path = self.input_image_list[self.image_index]
        filename, ext = os.path.splitext(file_path)

        output_path = os.path.join(self.temp_path, filename + ".csv")
        if os.path.exists(output_path):
            self.append_text_debugbox("load bounding box from : {}".format(output_path))
            self.bbox_df = pd.read_csv(output_path)
            for bbox_type in self.bbox_df.bbox_type.values:
                self.set_bbox_mask(int(bbox_type))


    def set_bbox_mask(self,bbox_type,color=1):
        revised_bbox_df = self.bbox_df.loc[self.bbox_df.bbox_type == bbox_type]
        bbox_img = np.zeros(self.cv_image.shape[:2],dtype=np.uint8)
        if not revised_bbox_df.empty:
            for _, row in revised_bbox_df.iterrows():
                start_point = (int(row.min_x),int(row.min_y))
                end_point = (int(row.max_x),int(row.max_y))
                cv2.rectangle(bbox_img,start_point,end_point,color=color, thickness=self.line_thickness)
        self.bbox_masks_dict[bbox_type] = bbox_img.copy()


    def load_contour_mask(self):
        file_path = self.input_image_list[self.image_index]
        filename, ext = os.path.splitext(file_path)

        output_path = os.path.join(self.temp_path, filename + ".npz")
        if os.path.exists(output_path):
            self.append_text_debugbox("load contour mask from : {}".format(output_path))
            npzfile = np.load(output_path)
            dict1, stack1 = npzfile['arr_0'], npzfile['arr_1']
            self.contour_point_dicts = dict1[()]
            self.contour_order_stack = stack1.tolist()

            for contour_type in self.contour_point_dicts:
                self.set_contour_mask(contour_type)


    def set_contour_mask(self,contour_type,color=1):
        contour_img = np.zeros(self.cv_image.shape[:2],dtype=np.uint8)
        if not contour_type in self.contour_point_dicts:
            self.contour_masks_dict[contour_type] = contour_img
        else:
            for contour_points in self.contour_point_dicts[contour_type]:
                cv2.fillPoly(contour_img,np.int32([contour_points]),color=color)

            if np.sum(contour_img) == 0 :
                if contour_type in self.contour_masks_dict:
                    self.contour_masks_dict.pop(contour_type,None)
            else:
                self.contour_masks_dict[contour_type] = contour_img


    def init_annotation_mask(self):
        # bbox의 내용들을 초기화
        self.bbox_masks_dict = {}
        self.bbox_df = None
        self.bbox_changed = False
        # contour의 내용들을 초기화
        self.contour_points = None
        self.contour_order_stack = []
        self.contour_point_dicts = {}
        self.contour_masks_dict = {}
        self.contour_changed = False


    ### 이미지 보정
    '''
    Annotating할 때, 병변 혹은 경계를 확인하기 쉽게 만들기 위해서
    이미지를 보정해주는 메소드들
    - adjust_image
        - adjust_clahe : CLAHE 알고리즘에 따라, 이미지의 경계를 보다 명료하게 만들어줌
        - adjust_gamma_correctin : 감마 보정 식에 따라, 이미지의 명도를 조절해줌
        - adjust_redfree_image : redfree 이미지로 바꾸어줌
    '''

    def adjust_image(self):
        image = self.cv_image.copy()
        image = self.adjust_clahe(image)
        image = self.adjust_gamma_correction(image)
        image = self.adjust_redfree_image(image)
        return image


    def adjust_clahe(self,image):
        if self.clahe_value == 0 :
            return image
        else:
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
            lab_planes = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(int(self.clahe_value),int(self.clahe_value)))
            lab_planes[0] = clahe.apply(lab_planes[0])
            lab = cv2.merge(lab_planes)
            return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


    def adjust_gamma_correction(self,image):
        # build a lookup table mapping the pixel values [0, 255] to
        # their adjusted gamma values
        invGamma = 1.0 / self.brightness_gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype(np.uint8)
        # apply gamma correction using the lookup table
        return cv2.LUT(image, table)


    def adjust_redfree_image(self,image):
        if self.redfree_or_not:
            # convert to Red-free Image
            rf_img = image.copy()
            rf_img[:,:,0] = 0
            return rf_img
        else :
            return image


    ### 키보드 및 마우스 조작 이벤트 리스너
    '''
    - canvas 관련 이벤트 리스너들
        - 키보드 관련된 이벤트 리스너
            - move_next_image
            - move_prev_image
            - reset_canvas
            - cancel_bbox_mask
            - cancel_contour_mask
            - cancel_current_contour
            - fill_in_contour
            - set_color_type

        - 마우스 관련된 이벤트 리스너
            - press_bbox
            - drag_bbox
            - drop_bbox
            - press_contour
            - drop_contour
            - drag_contour

    - Frame 관련 이벤트 리스너들
        - 디렉토리 설정 및 초기 세팅
                - select_input_directory :
                    annotating할 이미지가 담긴 디렉토리를 설정

                - set_output_directory :
                    작업한 결과물이 저장된 디렉토리 설정
                    input directory 내부에 저장

                    output 폴더 종류
                        - temp : 임시 작업 공간 (csv : bounding box의 좌표 저장, npz : contour의 좌표 저장 )
                        - bounding box : bounding box가 저장된 공간 (annotation type별로 저장)
                        - contour : contour area가 저장된 공간

                - set_first_image :
                    기작업한 내용 다음부터 시작하도록 설정(없으면 처음)

        - set_annotation_type
        - jump_to_image
        - set_line_thickness
        - set_blend_ratio
        - set_brightness
        - set_clahe
        - set_redfree
    '''
    #### canvas 관련 이벤트 리스너들
    def move_next_image(self,event):
        if self.image_index < len(self.input_image_list)-1:
            self.save_annotation_mask()
            self.init_annotation_mask()

            self.image_index += 1
            self.file_scale.set(self.image_index)
            self.clear_debugbox() # debugbox 내용 지우기
            self.show_canvas_image() # 이미지 보여주기
            self.show_preview_image() # 이미지의 원본 보여주기
            self.show_filename_text() # 현재 파일 순서 보여주기
            self.load_annotation_mask()
            self.show_annotation_mask()


    def move_prev_image(self,event):
        if self.image_index > 0:
            self.save_annotation_mask()
            self.init_annotation_mask()

            self.image_index -= 1
            self.file_scale.set(self.image_index)
            self.clear_debugbox() # debugbox 내용 지우기
            self.show_canvas_image() # 이미지 보여주기
            self.show_preview_image() # 이미지의 원본 보여주기
            self.show_filename_text() # 현재 파일 순서 보여주기
            self.load_annotation_mask()
            self.show_annotation_mask()


    def reset_canvas(self,event):
        self.init_annotation_mask()
        self.clear_debugbox() # debugbox 내용 지우기
        self.show_canvas_image() # 이미지 보여주기
        self.show_filename_text() # 현재 파일 순서 보여주기
        self.load_annotation_mask()
        self.show_annotation_mask()

        self.append_text_debugbox("reset canvas")


    def cancel_bbox_mask(self,event):
        # 현재 그린 바운딩 박스 중 마지막을 없앰
        ## bbox_dataframe에서 마지막을 제거
        if self.bbox_df is not None and not self.bbox_df.empty:
            removed_bbox_type = int(self.bbox_df.tail(1).bbox_type)
            self.bbox_df.drop(self.bbox_df.tail(1).index,inplace=True)
        else:
            # 비워져있으면 아무 작업 하지 않고 넘김
            return
        ## bbox_masks_dict에서 수정된 mask를 변경
        self.set_bbox_mask(removed_bbox_type)
        self.show_annotation_mask()
        self.bbox_changed = True

        self.append_text_debugbox("cancel the last of bounding boxes")


    def cancel_contour_mask(self,event):
        if self.contour is not None:
            self.cancel_current_contour()
        else:
            if len(self.contour_order_stack) >0 :
                contour_type = self.contour_order_stack.pop()

                if len(self.contour_order_stack) == 0:
                    self.contour_point_dicts.clear()
                    self.set_contour_mask(contour_type)
                    self.show_contour_mask()
                    self.contour_changed = True

                elif len(self.contour_point_dicts[contour_type]) > 0:
                    self.contour_point_dicts[contour_type].pop()
                    self.append_text_debugbox("cancel the last of contour masks")
                    self.set_contour_mask(contour_type)
                    self.show_contour_mask()
                    self.contour_changed = True


    def cancel_current_contour(self):
        self.contour_points = None
        self.canvas.delete(self.contour)
        self.contour = None
        self.append_text_debugbox("cancel current contour")


    def fill_in_contour(self,event):
        if self.contour_points is None:
            return

        # point들을 저장
        if self.contour_type in self.contour_point_dicts:
            self.contour_point_dicts[self.contour_type].append(self.contour_points)
        else:
            self.contour_point_dicts[self.contour_type] = [self.contour_points]
        # contour_type 순서를 저장
        self.contour_order_stack.append(self.contour_type)

        # contour image들을 저장
        if self.contour_type in self.contour_masks_dict:
            contour_img = self.contour_masks_dict[self.contour_type]
            cv2.fillPoly(contour_img,np.int32([self.contour_points]),color=1)
            self.append_text_debugbox("fill in contour type : {} | size : {}".format(self.contour_type,np.sum(contour_img)))
            self.contour_masks_dict[self.contour_type] = contour_img.copy()
        else:
            contour_img = np.zeros(self.cv_image.shape[:2],dtype=np.uint8)
            cv2.fillPoly(contour_img,np.int32([self.contour_points]),color=1)
            self.append_text_debugbox("fill in contour type : {} | size : {}".format(self.contour_type,np.sum(contour_img)))
            self.contour_masks_dict[self.contour_type] = contour_img.copy()

        self.contour_changed = True
        self.contour_points = None
        self.cancel_current_contour()
        self.show_contour_mask()


    def set_color_type(self,event):
        event_char = event.char
        if re.compile("^\d$").match(event_char):
            if self.annotation_type == TYPE_OPTION[0]:
                self.bbox_type = int(event_char)
                self.append_text_debugbox("set bbox_type : {}".format(self.bbox_type))
            elif self.annotation_type == TYPE_OPTION[1]:
                self.contour_type = int(event_char)
                self.append_text_debugbox("set contour type : {}".format(self.contour_type))


    def press_bbox(self,event):
        #bounding_box의 시작. 눌렀을 때 bbox 생성
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        self.bbox = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x+1, self.start_y+1, outline=self.bbox_color)


    def drag_bbox(self,event):
        # bbox를 drag할 때, bbox size가 변화하도록 함
        curX = self.canvas.canvasx(event.x)
        curY = self.canvas.canvasy(event.y)
        self.canvas.coords(self.bbox, self.start_x, self.start_y, curX, curY)


    def add_bbox_mask(self):
        if self.bbox_df.empty:
            return
        # 가장 최근에 들어온 것을 bbox_masks_dict에 추가함
        row = self.bbox_df.iloc[-1]
        bbox_type = int(row.bbox_type)
        start_point = (int(row.min_x),int(row.min_y))
        end_point = (int(row.max_x),int(row.max_y))
        if bbox_type in self.bbox_masks_dict:
            bbox_img = self.bbox_masks_dict[bbox_type]
            cv2.rectangle(bbox_img,start_point,end_point,1,self.line_thickness)
            self.bbox_masks_dict[bbox_type] = bbox_img.copy()
        else:
            bbox_img = np.zeros(self.cv_image.shape[:2],dtype=np.uint8)
            cv2.rectangle(bbox_img,start_point,end_point,1,self.line_thickness)
            self.bbox_masks_dict[bbox_type] = bbox_img.copy()


    def drop_bbox(self,event):
        # bbox를 drop했을 때, 이 포인트들을 저장
        self.canvas.delete(self.bbox)
        self.bbox = None

        min_x, max_x = min(self.start_x, event.x), max(self.start_x, event.x)
        min_y, max_y = min(self.start_y, event.y), max(self.start_y, event.y)

        row = { "bbox_type" : self.bbox_type, "min_x" : min_x, "min_y" : min_y,
                "max_x" : max_x, "max_y" : max_y}

        # initialize bbox_df
        if self.bbox_df is None:
            self.bbox_df = pd.DataFrame(columns=['bbox_type','min_x','min_y','max_x','max_y'])

        self.bbox_df = self.bbox_df.append(row,ignore_index=True)

        self.add_bbox_mask() # bbox_mask의 내용에 추가
        self.show_annotation_mask() # bbox_mask를 보여주기
        self.bbox_changed = True


    def press_contour(self,event):
        #contour의 시작. 눌렀을 때 line 생성
        curr_point = np.array([self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)],dtype=np.int32)

        if self.contour_points is None:
            self.contour_points = curr_point
            self.contour = self.canvas.create_line(*curr_point.tolist(),*curr_point.tolist(),
                smooth=True,fill='green',width = self.line_thickness)
        else:
            self.contour_points = np.vstack([self.contour_points,curr_point])
            self.canvas.coords(self.contour, *self.contour_points.reshape(-1).tolist())


    def drag_contour(self,event):
        # bbox를 drag할 때, bbox size가 변화하도록 함
        curr_point = np.array([self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)],dtype=np.int32)

        self.contour_points = np.vstack([self.contour_points,curr_point])
        self.canvas.coords(self.contour, *self.contour_points.reshape(-1).tolist())
        pass


    def drop_contour(self,event):
        pass

    #### Frame 관련 이벤트 리스너들
    def select_input_directory(self,event=None):
        # 조작할 이미지가 담겨있는 directory를 설정
        self.image_dir_path = filedialog.askdirectory()
        if self.image_dir_path == "" or self.image_dir_path is None:
            return
        self.input_image_list =[file_path for file_path in os.listdir(self.image_dir_path)\
        if (os.path.splitext(file_path)[1].lower() == '.jpg') or (os.path.splitext(file_path)[1].lower() == '.png')]

        self.file_scale.configure(to=(len(self.input_image_list)-1))

        self.input_image_list.sort()

        self.set_output_directory() # 저장할 위치 설정
        self.set_first_image() # 처음 보여줄 이미지를 설정
        self.bind_key_to_canvas() # 설정 키들을 canvas와 연결(event listener를 설정하는 것과 비슷)
        self.clear_debugbox() # debugbox 내용 지우기

        self.append_text_debugbox("input directory : {}".format(self.image_dir_path))
        self.append_text_debugbox("the number of image : {}".format(len(self.input_image_list)))

        self.show_canvas_image() # 이미지 보여주기
        self.show_preview_image()
        self.show_filename_text() # 현재 파일 순서 보여주기
        self.load_annotation_mask() # 저장된 bbox_mask를 load함
        self.show_annotation_mask() # 저장된 bbox_mask를 Show함


    def set_output_directory(self):
        global TEMP_DIR, MASK_IMG_DIR, CONTOUR_IMG_DIR
        self.bbox_img_dir = os.path.join(self.image_dir_path,MASK_IMG_DIR)
        if not os.path.exists(self.bbox_img_dir):
            os.makedirs(self.bbox_img_dir)

        self.contour_img_dir = os.path.join(self.image_dir_path,CONTOUR_IMG_DIR)
        if not os.path.exists(self.contour_img_dir):
            os.makedirs(self.contour_img_dir)

        self.temp_path = os.path.join(self.image_dir_path,TEMP_DIR)
        if not os.path.exists(self.temp_path):
            os.makedirs(self.temp_path)


    def set_first_image(self):
        # 처음 보여줄 이미지를 설정
        output_image_list = [os.path.splitext(file_path)[0] for file_path in os.listdir(self.temp_path)\
        if os.path.splitext(file_path)[1].lower() == '.csv' or os.path.splitext(file_path)[1].lower() == '.npz']
        # csv 파일 : bounding box 정보가 저장된 위치
        # npz 파일 : contour 정보가 저장된 위치
        input_image_list = [os.path.splitext(file_path)[0] for file_path in self.input_image_list]
        if len(output_image_list) == 0:
            self.image_index = 0
            self.file_scale.set(self.image_index)
            return
        else:
            # 이미 작업한 목록을 불러옴
            done_list = list(set(input_image_list)&set(output_image_list))
            if len(done_list) == 0:
                # 이미 작업한 목록이 없으면, 처음부터 시작.
                self.image_index = 0
                self.file_scale.set(self.image_index)
                return
            else:
                # 이미 작업한 목록이 있으면, 가장 마지막 것의 다음번째 부터 시작.
                done_list.sort()
                done_file_name = done_list[-1]
                self.image_index = input_image_list.index(done_file_name)
                if self.image_index != len(input_image_list)-1:
                    self.image_index += 1
                self.file_scale.set(self.image_index)

                return

    def set_annotation_type(self,event=None):
        if event in TYPE_OPTION:
            self.annotation_type = event
        self.bind_key_to_canvas()

        self.show_canvas_image()
        self.load_annotation_mask()
        self.show_annotation_mask()


    def jump_to_image(self,event):
        jumped_idx = int(event)
        if self.input_image_list is None or len(self.input_image_list) == 0 :
            # 아직 directory 결정이 안되었을 경우,
            # input image list가 0 인 경우
            return
        self.save_annotation_mask()
        self.init_annotation_mask()

        self.image_index = jumped_idx
        self.clear_debugbox()
        self.show_canvas_image() # 이미지 보여주기
        self.show_preview_image() # 이미지의 원본 보여주기
        self.show_filename_text() # 현재 파일 순서 보여주기
        self.load_annotation_mask()
        self.show_annotation_mask()


    def set_line_thickness(self,event):
        re_num = re.compile("^[0-9]$")
        if re_num.match(str(event)):
            self.line_thickness = int(event)
            if self.bbox_df is None or self.bbox_df.empty:
                return
            for bbox_type in self.bbox_df.bbox_type.values:
                self.set_bbox_mask(int(bbox_type))
            self.show_annotation_mask() # 저장된 bbox_mask를 Show함
            self.append_text_debugbox("set bounding box thickness : {}".format(str(event)))


    def set_blend_ratio(self,event):
        re_num = re.compile("^\d*(\.?\d*)$")
        if re_num.match(str(event)):
            self.blend_ratio = float(event)
            self.show_canvas_image()
            self.show_annotation_mask()
            self.append_text_debugbox("set blend ratio : {}".format(str(event)))


    def set_brightness(self,event):
        re_num = re.compile("^\d*(\.?\d*)$")
        if re_num.match(str(event)):
            self.brightness_gamma = float(event)
            self.show_canvas_image()
            self.show_annotation_mask()
            self.append_text_debugbox("set brightness : {}".format(str(event)))


    def set_clahe(self,event):
        re_num = re.compile("^\d+$")
        if re_num.match(str(event)):
            self.clahe_value = int(event)
            self.show_canvas_image()
            self.show_annotation_mask()
            self.append_text_debugbox("set clahe tile size : {}".format(str(event)))


    def set_redfree(self):
        if self.check_rf.get() == 1:
            self.redfree_or_not = True
        else :
            self.redfree_or_not = False

        self.show_canvas_image() # 이미지 보여주기
        self.show_annotation_mask() # 저장된 bbox_mask를 Show함
        self.append_text_debugbox("Convert to red-free image : {}".format(self.redfree_or_not))


if __name__ == "__main__":
    root =Tk()
    app = Application(root)
    root.mainloop()