# -*- coding:utf-8 -*-
# reference : https://spoqa.github.io/2013/05/21/py2exe-and-py2app.html

## reference 2: https://m.blog.naver.com/PostView.nhn?blogId=mandori21&logNo=220372958993&proxyReferer=https%3A%2F%2Fwww.google.co.kr%2F
from distutils.core import setup
import py2exe

from tkinter import *
from PIL import Image
from PIL import ImageTk
from tkinter import filedialog
import cv2

import numpy as np
import pandas as pd

import sys
import os
import re
import csv

from itertools import zip_longest


includes = [
    "encodings",
    "encodings.utf_8",
]

options = {
    "bundle_files":1, # create singlefile exe
    "compressed":1,    # compress the library archive
    "optimize":2,      # do optimize
    "includes":includes,
}

setup(
    name = "draw_fundus_mask",
    description = "drawing the label of fundus image",
    version="0.0.1",
    options = {"py2exe":options},
    windows = [{"script":"draw_window.py",
                "icon_resources":[(1,"./icon.ico")],
                "dest_base":"drawing_fundus"}],
    zipfile = None
)