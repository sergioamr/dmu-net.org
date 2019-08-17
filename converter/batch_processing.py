﻿###########################################################################################
##Copyright 2017 Jonathan DEKHTIAR (contact@jonathandekhtiar.eu; jonathan.dekhtiar@utc.fr)
###########################################################################################
##This file is part of pythonOCC.
##
##pythonOCC is free software: you can redistribute it and/or modify
##it under the terms of the GNU Lesser General Public License as published by
##the Free Software Foundation, either version 3 of the License, or
##(at your option) any later version.
##
##pythonOCC is distributed in the hope that it will be useful,
##but WITHOUT ANY WARRANTY; without even the implied warranty of
##MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##GNU Lesser General Public License for more details.
##
##You should have received a copy of the GNU Lesser General Public License
##along with pythonOCC.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

import os, sys, time, random, string, errno, csv
from shutil import copyfile, rmtree
from uuid import uuid4

# ======== OCC - Display Libraries ========
from OCC.Display.SimpleGui import init_display

from OCC.Core.Visual3d import *
from OCC.Core.Quantity import *
from OCC.Core.Aspect import *
from OCC.Core.Graphic3d import *

# ======== OCC - STEP AP203 Libraries ========
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity

# ======== OCC - STL Libraries ========
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.TopoDS import TopoDS_Shape

# ======== OCC - Model Export Libraries ========
from OCC.Display.WebGl import threejs_renderer
from OCC.Core.Visualization import Tesselator

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.StlAPI import StlAPI_Writer

# ========== PyQt - Window ================

from PyQt5 import QtGui, QtWidgets, QtCore

# ========== Logging ============

import logging

# création de l'objet logger qui va nous servir à écrire dans les logs
log = logging.getLogger(__name__)
# on met le niveau du logger à ERROR, comme ça il n'écrit que les erreurs importantes
log.setLevel(logging.ERROR)

# ################################################################################
# ====================== File/Folder Manipulation Functions ======================
# ################################################################################

def getDirs(path) :
    dirs = []
    listing = os.listdir(path)
    for d in listing:
        if os.path.isdir(path + "/" + d):
            dirs.append(d)
    return dirs

def getFiles(path) :
    files = []
    listing = os.listdir(path)
    for f in listing:
        if os.path.isfile(path + "/" + f):
            files.append(f)
    return files

def createDir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def silentRemove(filename):
    try:
        os.remove(filename)
    except OSError as e: # this would be "except OSError, e:" before Python 2.6
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            raise # re-raise exception if a different error occurred

def delete_directory(targeted_dir):
    try:
        rmtree(targeted_dir)
    except:
        pass

def id_generator(size=20, chars=string.ascii_uppercase + string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

# ################################################################################
# ======================= DMUNet_Parser - Class Definition =======================
# ################################################################################

class DMUNet_Parser:

    # ================================================================================
    # ============================ Class Specific Methods ============================
    # ================================================================================

    def __init__(self):
        # =========================== Defining Shape Color ===========================
        # DisplayColoredShape(Red[0,1], Green[0,1], Blue[0,1], Quantity_TypeOfColor)
        # Quantity_TypeOfColor => Quantity_TOC_RGB = 0,    Quantity_TOC_HLS = 1

        red_param         = 40.0/255
        green_param       = 40.0/255
        blue_param        = 40.0/255

        self._shape_color = Quantity_Color(
            red_param,
            green_param,
            blue_param,
            Quantity_TOC_RGB
        )

        # ======================= None Variable Initialization =======================
        self._shape        = None
        self._inputFile    = None
        self._outputFolder = None
        self._tess         = None

        # ========================== Display Initialization ==========================

        print("Init display")

        self._display, self._start_display, self._add_menu, self._add_function_to_menu = init_display("qt-pyqt5", size=(600, 600))

        print("Add menu")
        self._add_menu('DMU-Net')
        self._add_function_to_menu('DMU-Net', self.batch_processing)
        self._add_function_to_menu('DMU-Net', self.process_first_class)
        self._add_function_to_menu('DMU-Net', self.close_program)

        print("Set background color")
        self._set_background_color(255,255,255)

        print("TriedronErase")
        self._display.View.TriedronErase()


        self.batch_processing()
        self.close_program()

        ########

        app = QtWidgets.QApplication.instance()

        if not app:  # create QApplication if it doesnt exist
            raise Exception("QApplication does not exist")

        app_icon = QtGui.QIcon()
        app_icon.addFile('icons/16x16.png', QtCore.QSize(16,16))
        app_icon.addFile('icons/24x24.png', QtCore.QSize(24,24))
        app_icon.addFile('icons/32x32.png', QtCore.QSize(32,32))
        app_icon.addFile('icons/48x48.png', QtCore.QSize(48,48))
        app_icon.addFile('icons/256x256.png', QtCore.QSize(256,256))
        app.setWindowIcon(app_icon)

        # =============================== Start Display ==============================
        self._start_display()

    def __enter__(self):
        return self

    # ================================================================================
    # ========================= Attribute-Validation Methods =========================
    # ================================================================================

    def _check_inputFile(self, function_name=""):
        if self._inputFile is None:
            raise Exception("'_inputFile' is None - Method: " + function_name)

        elif not os.path.isfile(self._inputFile) :
            raise Exception("'_inputFile' is None - Method: " + function_name)

        else:
            return True

    def _check_outDir(self, function_name=""):
        if self._outputFolder is None:
            raise Exception("'_outputFolder' is None - Method: " + function_name)
        else:
            createDir(self._outputFolder)
            return True

    def _check_shape(self, function_name=""):
        if self._shape is None:
            raise Exception("'_shape' is None - Method: " + function_name)
        else:
            return True

    def _check_display(self, function_name=""):
        if self._display is None:
            raise Exception("'_display' is None - Method: " + function_name)
        else:
            return True

    def _check_exist_inputFile_AND_outDir(self, function_name=""):
        return self._check_inputFile(function_name) and self._check_outDir(function_name)

    # ================================================================================
    # ============================ Display-Related Methods ===========================
    # ================================================================================

    def _set_background_color(self, red=122, green=122, blue=122):

        if self._check_display("_set_background_color"):
            # display.set_bg_gradient_color(Red1, Green1, Blue1, Red2, Green2, Blue2)
            # => Gradient between color1 & color2
            # => if color1 = color2 => No gradient

            self._display.set_bg_gradient_color([red, green, blue], [red, green, blue-2])

    def _set_background_image(self, bg_image='bg.jpg'): #Not used for now

        if self._check_display("_set_background_image"):

            if os.path.isfile(bg_image):
                self._display.SetBackgroundImage(bg_image)
            else:
                raise Exception("'bg_image' given does not exist - Method: _set_background_image")

    def _take_screenshot(self, outname="screenshot", extension="png"):

        if self._check_display("_take_screenshot"):
            extension = extension.lower()

            if extension in ["png", "bmp", "jpeg", "tiff"] and self._check_outDir("_take_screenshot"):
                self._display.View.Dump(os.path.join(self._outputFolder, outname + '.' + extension))
                return True

            else:
                raise Exception ('Unknown extension, only ["png", "bmp", "jpeg", "tiff"] allowed')

    def close_program(self):
        sys.exit(0)

    # ================================================================================
    # ============================= Shape-Related Methods ============================
    # ================================================================================

    def _display_shape(self):

        if self._check_display("_display_shape") and self._check_shape("_display_shape"):
            self._display.DisplayColoredShape(self._shape, color=self._shape_color, update=True)
            #self._display.DisplayColoredShape(self._shape)
            self._display.View_Iso()
            self._display.FitAll()
            print("DISPLAY ALL")
            self._display.SelectArea(0,0,600,600) #Make selection viewable.

    def _remove_shape(self):

        if self._check_display("_remove_shape"):
            self._display.EraseAll()

    # ================================================================================
    # ============================= Model-Loading Methods ============================
    # ================================================================================

    def _load_model_file(self): # STEP & STL Files

        if  self._check_inputFile("_load_model_file"):

            filename, file_extension = os.path.splitext(self._inputFile)

            if file_extension == '.stl':
                return self._load_STL_file()

            elif file_extension in ['.step', '.stp']:
                return self._load_STEP_file()

            else:
                raise Exception("File Extension not supported: " + file_extension + ' - Method: _load_STEP_file')

    def _load_STEP_file(self): # STEP Files

        if  self._check_inputFile("_load_STEP_file"):

            step_reader = STEPControl_Reader()
            status = step_reader.ReadFile(self._inputFile)

            if status == IFSelect_RetDone:  # check status
                failsonly = False
                step_reader.PrintCheckLoad(failsonly, IFSelect_ItemsByEntity)
                step_reader.PrintCheckTransfer(failsonly, IFSelect_ItemsByEntity)

                ok = step_reader.TransferRoot(1)
                _nbs = step_reader.NbShapes()

                self._shape = step_reader.Shape(1)
                return True

            else:
                raise Exception("Error: can't read file - Method: _load_STEP_file")

    def _load_STL_file(self): # STL Files

        if  self._check_inputFile("_load_STL_file"):

            stl_reader = StlAPI_Reader()
            shape = TopoDS_Shape()

            stl_reader.Read(shape, self._inputFile)

            self._shape = shape
            return True

    # ================================================================================
    # ============================ CSV Recording Methods =============================
    # ================================================================================

    def _createRsltDict(self, category, original_partname, partname, format):
        sub_rslt = dict()

        sub_rslt["idPart"] = None
        sub_rslt["name"] = partname
        sub_rslt["original_partName"] = original_partname
        sub_rslt["format"] = format.upper()
        sub_rslt["category"] = category

        return sub_rslt

    # ================================================================================
    # ============================ 3D Model Export Methods =============================
    # ================================================================================


    def _exportSTL(self, outname="shape.stl"):
            # Export to STL
            stl_writer = StlAPI_Writer()
            stl_writer.SetASCIIMode(True)

            path = os.path.join(self._outputFolder, outname)
            stl_writer.Write(self._shape,path)

    def _exportThreeJS(self, outname="shape.json"):
        if self._check_shape("_exportThreeJS") and self._check_outDir("_exportThreeJS"):

            if self._tess is None:
                self._tess = Tesselator(self._shape)
                self._tess.Compute(uv_coords=False, compute_edges=False, mesh_quality=50)

            #self._tess.ExportShapeToThreejs(self._outputFolder + '/' + outname)
            with open(os.path.join(self._outputFolder, outname), "w") as text_file:
                json_shape = self._tess.ExportShapeToThreejsJSONString(self._inputFile)

                json_shape = json_shape.replace("data\\", "data/")
                json_shape = json_shape.replace("\\step_postprocessed\\", "/step_postprocessed/")

                text_file.write(json_shape)

    def _exportX3D(self, outname="shape.x3dom"):
        if self._check_shape("_exportX3D") and self._check_outDir("_exportX3D"):

            if self._tess is None:
                self._tess = Tesselator(self._shape)
                self._tess.Compute(uv_coords=False, compute_edges=False, mesh_quality=50)

            self._tess.ExportShapeToX3D(os.path.join(self._outputFolder, outname))

    def _copy_model_to_outdir(self, outname="part"):
        if self._check_inputFile("_copy_model_to_outdir") and self._check_outDir("_copy_model_to_outdir"):
            filename, file_extension = os.path.splitext(self._inputFile)

            if file_extension in ['.stl', '.step', '.stp']:
                copyfile(self._inputFile, os.path.join(self._outputFolder, outname + file_extension))

            else:
                raise Exception("File Extension not supported: " + file_extension)


    # ================================================================================
    # =========================== Model-Processing Methods ===========================
    # ================================================================================

    def _model_processing(self, inputFile=None, outputFolder=None):

        self._inputFile     = inputFile
        self._outputFolder  = outputFolder

        if self._check_inputFile("_model_processing") and self._check_outDir("_model_processing"):

            if self._load_model_file():

                self._display_shape()
                self._take_screenshot()
                self._exportThreeJS()
                self._exportSTL()
                self._exportX3D()
                self._copy_model_to_outdir()
                #self._remove_shape()

            else:
                raise Exception("Error While Loading Model - _model_processing()")

            self._inputFile     = None
            self._outputFolder  = None
            self._shape         = None
            self._tess          = None

    def process_first_class(self):
        self.batch_processing(convert_only_first_folder = True)

    def batch_processing(self, convert_only_first_folder = False):
        print("BATCH PROCESSING")
        input_directory   = "data"
        output_directory  = "output"
        output_CSVFile    = "total.csv"

        # ========================== CLEANING STEP ============================

        ### Removing Output Directory
        delete_directory(output_directory)

        # ========================= BATCH PROCESSING ===========================

        keys = ["idPart", "name", "original_partName", "format", "category"]

        ### Removing CSV Output File
        print("Remove " + output_CSVFile)
        silentRemove(output_CSVFile)

        with open(output_CSVFile, 'w') as csvfile:
            print("Write header")
            writer = csv.DictWriter(csvfile, fieldnames=keys, lineterminator='\n', quoting=csv.QUOTE_NONE)
            writer.writeheader()

        subDirs = getDirs(input_directory)

        print("subdirs")
        for d in subDirs :

            ##### Creating CSV File for Outputs

            class_CSVFile = d.lower() + ".csv"

            ### Removing CSV Output File
            silentRemove(class_CSVFile)

            ### Adding headers to the CSV File

            with open(class_CSVFile, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=keys, lineterminator='\n', quoting=csv.QUOTE_NONE)
                writer.writeheader()

            ### Getting all the files for a given class

            models_path = os.path.join(input_directory, d, "step_postprocessed")

            files = getFiles(models_path)

            for model_file in files :

                filename, file_extension = os.path.splitext(model_file.lower())

                if not (file_extension in [".stl", ".step", ".stp"]):
                    continue

                while (True):
                    generated_name = ""
                    out_processing_dir = os.path.join(output_directory, d, generated_name)

                    print ("OUT " + out_processing_dir)

                    if not os.path.exists(out_processing_dir):
                        break

                model_path = os.path.join(models_path, model_file)
                print (model_path)

                print ("Mode " + model_path)
                self._model_processing(model_path, out_processing_dir)

                print(self._createRsltDict(d, model_file, generated_name, file_extension[1:]))

                result_arr = self._createRsltDict(
                    d, #category
                    model_file, #original_partname
                    generated_name, #partname
                    file_extension[1:] #format
                )

                with open(class_CSVFile, 'a') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=keys, lineterminator='\n', quoting=csv.QUOTE_NONE)
                    writer.writerow(result_arr)

                with open(output_CSVFile, 'a') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=keys, lineterminator='\n', quoting=csv.QUOTE_NONE)
                    writer.writerow(result_arr)

                    print ("Write " + output_CSVFile)

            if (convert_only_first_folder):
                break
# ================================================================================
# =========================== Model-Processing Methods ===========================
# ================================================================================

def id_generator(size=20, chars=string.ascii_uppercase + string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

if __name__ == "__main__":
    try:
        print("PARSET")
        parser = DMUNet_Parser()
    except Exception as e:
        print ("Error", str(e))