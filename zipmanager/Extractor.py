
from PySide2 import QtWidgets, QtGui, QtCore
from CustomWidgets import TreeWidget, ProgressUpdater, KillableThread, ComboBoxAction, SpinBoxAction, CheckBoxAction
from functools import partial
from Tools import *
#from Tools import log, debugging, _platform, getFileIcon, getPath, openOnExplorer, notify, settings, tempDir
import os, zipfile, time, sys
from sys import platform as _platform
from threading import Thread
import subprocess
from qt_thread_updater import get_updater


class Extractor(QtWidgets.QWidget):
    throwInfoSignal = QtCore.Signal(str, str)
    throwWarningSignal = QtCore.Signal(str, str)
    throwErrorSignal = QtCore.Signal(str, str)
    
    updateProgressBar = QtCore.Signal([int, int], [int, int, str])
    
    changeItemIcon = QtCore.Signal(QtWidgets.QTreeWidgetItem, int, str)
    changeItemText = QtCore.Signal(QtWidgets.QTreeWidgetItem, int, str)

    stopLoadingSignal = QtCore.Signal()


    def __init__(self, parent=None, startFile: str = ""):
        super().__init__(parent=parent)
        self.window = parent
        self.isExtracting = False
        self.errorWhileCompressing = None
        self.compression_level = 5
        self.files = []
        self.zip = ""
        self.setUpToolBar()
        self.setUpWidgets()
        self.throwInfoSignal.connect(self.throwInfo)
        self.throwWarningSignal.connect(self.throwWarning)
        self.throwErrorSignal.connect(self.throwError)

        self.updateProgressBar[int, int].connect(self.updateProgressBarValue)
        self.updateProgressBar[int, int, str].connect(self.updateProgressBarValue)

        self.stopLoadingSignal.connect(self.stopLoading)

        if(startFile != ""):
            self.openZip(startFile)
    
    def throwInfo(self, title: str, body: str) -> None:
        try:
            self.window.throwInfo(title, body)
        except AttributeError:
            log(f"[ FAILED ] Unable to show info message!!!\n\n[                   ] Info: {body}")
    
    def throwError(self, title: str, body: str) -> None:
        try:
            self.window.throwError(title, body)
        except AttributeError as e:
            log(f"[ FAILED ] Unable to show error message!!!\n\n[                   ] Info: {body}")
            if(debugging):
                raise e

    def throwWarning(self, title: str, body: str) -> None:
        try:
            self.window.throwWarning(title, body)
        except AttributeError:
            log(f"[ FAILED ] Unable to show warning message!!!\n\n[                   ] Info: {body}")

    def setUpToolBar(self) -> None:
        self.toolBar = QtWidgets.QToolBar(self)
        self.toolBar.setIconSize(QtCore.QSize(24, 24))
        self.toolBar.setContentsMargins(0, 0, 0, 0)

        self.addFileAction = QtWidgets.QAction("Open zip file", self)
        self.addFileAction.setToolTip("Open zip file")
        self.addFileAction.setIcon(QtGui.QIcon(getPath("openzip.ico")))
        self.addFileAction.triggered.connect(lambda: self.openZip())
        self.toolBar.addAction(self.addFileAction)

        self.toolBar.addSeparator()

        self.subdircheck = CheckBoxAction(self, "Extract on a new folder: ", settings["create_subdir"])
        self.toolBar.addWidget(self.subdircheck)

        self.toolBar.addSeparator()

        self.openFilesAction = QtWidgets.QAction("Open with default application", self)
        self.openFilesAction.setToolTip("Open with default application")
        self.openFilesAction.setIcon(QtGui.QIcon(getPath("window.ico")))
        self.openFilesAction.triggered.connect(self.openItemFile)
        self.toolBar.addAction(self.openFilesAction)
        
        self.toolBar.addSeparator()

        self.magicAction = QtWidgets.QAction("Compress", self)
        self.magicAction.setToolTip("Compress")
        self.magicAction.setIcon(QtGui.QIcon(getPath("extractFiles.ico")))
        self.magicAction.triggered.connect(self.magicButtonAction)
        self.toolBar.addAction(self.magicAction)

    def setUpWidgets(self) -> None:

        log("[        ] Now loading widgets...")

        self.treeWidget = TreeWidget(self)
        self.treeWidget.setSortingEnabled(True)
        self.treeWidget.setEmptyText("Select a zip file to start")
        self.treeWidget.connectFileDragEvent(self.openZip)
        self.treeWidget.setHeaderLabels(["Name", "Size", "Extract or skip"])
        self.treeWidget.setColumnHidden(3, True)
        self.treeWidget.setColumnHidden(4, True)
        self.treeWidget.itemDoubleClicked.connect(self.openItemFile)
        self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)  
        self.treeWidget.customContextMenuRequested.connect(self.showRightClickMenu)

        self.magicButton = QtWidgets.QPushButton(self)
        self.magicButton.setFixedHeight(25)
        self.magicButton.setText("Extract")
        self.magicButton.clicked.connect(self.magicButtonAction)

        self.currentStatusBar = ProgressUpdater(self, self.window, "Extracting...", "Click extract to start")
        
        self.horLayout1 = QtWidgets.QHBoxLayout()

        verLayout1 = QtWidgets.QVBoxLayout()
        verLayout2 = QtWidgets.QVBoxLayout()


        self.zipFileInfo = QtWidgets.QGroupBox()
        self.zipFileInfo.setTitle("Zip file information")
        self.infoLayout = QtWidgets.QFormLayout()
        self.zipFileInfo.setLayout(self.infoLayout)
        self.zipFileInfo.setFixedWidth(256)


        self.zipName = QtWidgets.QLineEdit()
        self.zipName.setFocusPolicy(QtCore.Qt.NoFocus)
        self.infoLayout.addRow("Zip name:", self.zipName)

        self.zipPath = QtWidgets.QLineEdit()
        self.zipPath.setFocusPolicy(QtCore.Qt.NoFocus)
        self.infoLayout.addRow("Zip location:", self.zipPath)
        
        self.zipSize = QtWidgets.QLineEdit()
        self.zipSize.setFocusPolicy(QtCore.Qt.NoFocus)
        self.infoLayout.addRow("Compressed size:", self.zipSize)
        
        self.zipRealSize = QtWidgets.QLineEdit()
        self.zipRealSize.setFocusPolicy(QtCore.Qt.NoFocus)
        self.infoLayout.addRow("Real size:", self.zipRealSize)
        
        self.zipRate = QtWidgets.QLineEdit()
        self.zipRate.setFocusPolicy(QtCore.Qt.NoFocus)
        self.infoLayout.addRow("Compression rate:", self.zipRate)
        
        self.zipAlgorithm = QtWidgets.QLineEdit()
        self.zipAlgorithm.setFocusPolicy(QtCore.Qt.NoFocus)
        self.infoLayout.addRow("Used algoritms: ", self.zipAlgorithm)




        verLayout1.addWidget(self.zipFileInfo)
        verLayout1.addWidget(self.magicButton)
        verLayout2.addWidget(self.treeWidget)
        verLayout2.addWidget(self.currentStatusBar)

        self.horLayout1.addLayout(verLayout1)
        self.horLayout1.addLayout(verLayout2, strech=1)

        self.mainVerLayout = QtWidgets.QVBoxLayout(self)
        self.mainVerLayout.addWidget(self.toolBar)
        self.mainVerLayout.addLayout(self.horLayout1)

        self.setLayout(self.mainVerLayout)

    def magicButtonAction(self) -> None:
        if not(self.isExtracting):
            self.startLoading()
        else:
            self.stopLoading()
    
    def startLoading(self) -> None:
        self.magicButton.setText("Cancel extraction")
        self.isExtracting = True
        self.treeWidget.expandAll()
        self.currentStatusBar.startLoading()
        self.addFileAction.setEnabled(False)
        self.subdircheck.setEnabled(False)
        self.magicAction.setText("Cancel Extraction")
        self.magicAction.setToolTip("Cancel Extraction")
        self.magicAction.setIcon(QtGui.QIcon(getPath("cancelCompress.ico")))
        self.extractZip()
    
    def stopLoading(self) -> None:
        self.magicButton.setText("Extract")
        self.isExtracting = False
        self.treeWidget.setEnabled(True)
        self.addFileAction.setEnabled(True)
        self.subdircheck.setEnabled(True)
        self.magicAction.setText("Extract")
        self.magicAction.setToolTip("Extract")
        self.magicAction.setIcon(QtGui.QIcon(getPath("extractFiles.ico")))
        self.currentStatusBar.stopLoading()
    
    def openItemFile(self) -> None:
        item = self.treeWidget.currentItem()
        if(item.text(1)!=""):
            log("[        ] Opening file with default app...")
            archive = zipfile.ZipFile(self.zip)
            print(archive.namelist())
            self.openOSFileDirectly(archive.extract(item.text(5), tempDir.name))
            archive.close()
    
    def updateProgressBarValue(self, actual: int, total: int, actualFile=""):
        if(actualFile!=""):
            try:
                size = os.path.getsize(actualFile)
                size = size/1000
                if(size<1000):
                    fsize = f"{size:.2f} KB"
                else:
                    fsize = f"{size/1000:.2f} MB"

            except FileNotFoundError:
                fsize = "0 B"
            self.currentStatusBar.infoLabel.setText(f"Extracting file \"{actualFile}\" ({fsize}, {actual} out of {total})")
        else:
            self.currentStatusBar.infoLabel.setText("Extracting...")
        self.currentStatusBar.setRange(0, total)
        self.currentStatusBar.setValue(actual)

    def showRightClickMenu(self, pos: QtCore.QPoint) -> None:
        x = 0
        x = 0
        x += self.treeWidget.pos().x()
        x += self.window.pos().x()
        x += pos.x()
        y = 0
        y += 90 # Tab widget + menubar
        y += self.treeWidget.pos().y()
        y += self.window.pos().y()
        y += pos.y()
        log(f"[        ] Showing menu at {x}x{y}")
        menu = QtWidgets.QMenu(self)
        menu.move(x, y)

        menu.addAction(self.addFileAction)
        
        menu.addSeparator()

        menu.addAction(self.openFilesAction)

        menu.addSeparator()

        menu.addAction(self.magicAction)

        menu.exec_()
    
    def openOSFileDirectly(self, file: str) -> None:
        log(f"[        ] Spawining process to open file {file}")
        if(_platform=="win32"):
            c = os.system(f"start \"\" \"{file}\"")#, shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        elif(_platform=="darwin"):
            c = os.system(f"open \"{file}\"")
            #c = subprocess.run(f"open \"{file}\"", shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        else:
            c = os.system(f"xdg-open \"{file}\"")
            #c = subprocess.run(f"xdg-open \"{file}\"", shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if(c != 0):
            self.throwError("Error opening file", f"Unable to open file \"{file}\"\n\nOutput code: \"{c.returncode}\"\n\nError Details: \n\"{str(c.stdout)}\"")
        else:
            log("[   OK   ] File opened succesfully (exit code is 0)")

    def openZip(self, filepath: str = "") -> None:
        try:
            if(filepath != ""):
                if(_platform=="win32" and filepath[0]=="/"):
                    filepath = filepath[1:]
                filepath = [filepath]
                log('[   OK   ] Zip file given by commandline')
            else:
                log('[        ] Dialog in process')
                filepath = QtWidgets.QFileDialog.getOpenFileName(self.parent(), "Select a zip file to extract it", "", "Zip Files (*.zip);;All files (*.*)")
                if(filepath[0] == ""):
                    log("[  WARN  ] User aborted the dialog")
                    return
            file = open(filepath[0], 'r')
            log('[   OK   ] Dialog Completed')
            supposedZip = str(file.name)
            log('[        ] Closing file')
            file.close()
            log('[   OK   ] File Closed.')
            if not zipfile.is_zipfile(supposedZip):
                self.throwError("Error", f"The file {supposedZip} is not a valid zip file!")
                return
            else:
                self.treeWidget.clear()
                zip = supposedZip.replace("\\", "/")
                self.zip = zip
                zipFile = zipfile.ZipFile(zip)

                size = 0
                compSize = 0

                deflate, lzma, bzip2, stored = False, False, False, False

                for element in zipFile.infolist():
                    compSize += element.compress_size
                    size += element.file_size
                    if not(deflate):
                        if(element.compress_type == zipfile.ZIP_DEFLATED):
                            deflate = True
                    if not(lzma):
                        if(element.compress_type == zipfile.ZIP_LZMA):
                            lzma = True
                    if not(bzip2):
                        if(element.compress_type == zipfile.ZIP_BZIP2):
                            bzip2 = True
                    if not(stored):
                        if(element.compress_type == zipfile.ZIP_STORED):
                            stored = True

                zipAlgorithms = ""
                if(deflate):
                    zipAlgorithms += "Deflated; "
                if(lzma):
                    zipAlgorithms += "LZMA; "
                if(bzip2):
                    zipAlgorithms += "BZIP2; "
                if(stored):
                    zipAlgorithms += "Stored; "

                self.zipName.setText(zip.split("/")[-1])
                self.zipPath.setText('/'.join(zip.split("/")[:-1]))
                self.zipSize.setText(f"{compSize/1000000:.2f} MB")
                self.zipRealSize.setText(f"{size/1000000:.2f} MB")
                self.zipRate.setText(f"{compSize/size*100:.1f} %")
                self.zipAlgorithm.setText(zipAlgorithms)

                files = []
                folders = {}
                infos = []

                for file in zipFile.namelist():
                    if(file[-1] == "/"):
                        pass
                    else:
                        files.append(file.split('/'))
                        infos.append(zipFile.getinfo(file))
                
                infoindex = 0
                itemsToProcess = []
                for file in files:
                    try:
                        info = infos[infoindex]
                        i = 0
                        parentWidgets = []
                        while i<len(file):
                            path = file[i]
                            try:
                                parentWidgets.append(folders[path])
                                i += 1
                            except KeyError:
                                log(f"[        ] Adding item {path}")
                                item =  QtWidgets.QTreeWidgetItem()
                                item.setText(0, path)
                                item.setText(5, info.filename) 
                                if(i+1<len(file)):
                                    item.setText(1, "")
                                    try:
                                        item.setIcon(0, QtGui.QIcon(QtGui.QPixmap(getPath("folder.ico")).scaledToWidth(24, QtCore.Qt.SmoothTransformation)))
                                        item.setText(6, "folder")
                                    except:
                                        pass
                                else:
                                    item.setText(1, f"{info.file_size/1000000:.3f} MB")
                                    try:
                                        item.setIcon(0, QtGui.QIcon(getFileIcon(path)))
                                        item.setText(6, "file")
                                    except:
                                        pass
                                folders[path] = item
                                itemsToProcess.append(item)
                            

                        i = 0
                        while i<(len(parentWidgets)-1):
                            parentWidgets[i].addChild(parentWidgets[i+1])
                            i += 1

                        
                    except Exception as e:
                        self.throwError("SomePythonThings Zip Manager", f"Unable to load file {file}\n\nError Details:\n{str(e)}")
                        if(debugging):
                            raise e
                    infoindex += 1

                for folder in folders.values():
                    self.treeWidget.addTopLevelItem(folder)
                self.treeWidget.expandAll()
                print(itemsToProcess)
                for item in itemsToProcess:
                    def changeState(checkbox: QtWidgets.QCheckBox, item: QtWidgets.QTreeWidgetItem, _):
                        item.setDisabled(not(checkbox.isChecked()))
                        if(checkbox.isChecked()):
                            checkbox.setText("Extract")
                        else:
                            checkbox.setText("Skip")
                        for i in range(item.childCount()):
                            subitem = item.child(i)
                            subcheckbox = subitem.treeWidget().itemWidget(subitem, 2)
                            if(subcheckbox):
                                subitem.setDisabled(not(subcheckbox.isChecked()))
                                subcheckbox.setChecked(checkbox.isChecked())
                            else:
                                log("[  WARN  ] Unable to disable/enable other checkboxes")
                    checkbox = QtWidgets.QCheckBox()
                    checkbox.setChecked(True)
                    checkbox.setText("Extract")
                    checkbox.stateChanged.connect(partial(changeState, (checkbox), (item)))
                    item.treeWidget().setItemWidget(item, 2, checkbox)
        except Exception as e:
            self.throwError("SomePythonThings Zip Manager", "Unable to select zip file.\n\nReason:\n"+str(e))
            if(debugging):
                raise e



    def extractZip(self):
        zip = self.zip
        if(self.zip == ''):
            self.window.throwWarning("SomePythonThings Zip Manager", "Please select one zip file to start the extraction.")
            self.stopLoading()
        else:
            try:
                zip = zip.replace("\\", "/")
                log('[        ] Dialog in proccess')
                directory = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select the destination folder where the zip is going to be extracted', os.path.expanduser("~"))
                if(directory == ''):
                    log("[  WARN  ] User aborted the dialog")
                    return 0
                log('[   OK   ] zip file selected successfully')
                directory = str(directory)
                if not(directory == ''):
                    
                    print(directory)
                    if(self.subdircheck.isChecked()):
                        log("[        ] Creating subdirectory...")
                        directory += "/"+zip.split('/')[-1]+" - Extracted files"
                    log("[  INFO  ] Zip file will be extracted into "+directory)

                    def analyzeFileList(files: list, item: QtWidgets.QTreeWidgetItem):
                            if(item.childCount()>0):
                                for i in range(item.childCount()):
                                    files = analyzeFileList(files, item.child(i))
                            else:
                                files.append(item)
                            return files

                    files = []
                    for i in range(self.treeWidget.topLevelItemCount()):
                        files = analyzeFileList(files, self.treeWidget.topLevelItem(i))

                    Thread(target=self.heavyExtract, args=(directory, zip, files), daemon=True).start()
            except Exception as e:
                if debugging:
                    raise e
                log('[ FAILED ] Error occurred while extracting zip File')
                self.window.throwError("SomePythonThings Zip Manager", 'Unable to extract the zip\n\nReason:\n'+str(e))



    def pure_extract(self, zipObj, file, directory, passwd=""):
        self.errorWhileExtracting = None
        try:
            zipObj.extract(file, directory)
        except Exception as e:
            self.errorWhileExtracting = e

    def heavyExtract(self, directory, zip, files):
        try:
            error = False
            log('[        ] Extracting zip file on '+str(directory))
            archive = zipfile.ZipFile(zip)
            totalFiles = 0
            for file in archive.namelist():
                totalFiles += 1
            actualFile = 0
            self.errorWhileExtracting = None
            #if(password!=""):
            #    archive.setpassword(bytes(password, 'utf-8'))
            for file in files:
        
                if(file.treeWidget().itemWidget(file, 2).isChecked()):
                    file = file.text(5)
                    try:
                        self.updateProgressBar[int, int, str].emit(actualFile, totalFiles, file)
                        t = KillableThread(target=self.pure_extract, args=( archive, file, directory))
                        t.start()
                        while t.is_alive():
                            if not(self.isExtracting):
                                log("[  WARN  ] User canceled the zip extraction!")
                                self.stopLoadingSignal.emit()
                                t.shouldBeRuning=False
                                self.throwWarningSignal.emit("SomePythonThings Zip Manager", "User cancelled the zip extraction")
                                archive.close()
                                sys.exit("User killed zip creation process")
                            else:
                                time.sleep(0.01)
                        t.join()
                        if(self.errorWhileExtracting!=None):
                            raise self.errorWhileExtracting
                        log('[   OK   ] File '+file.split('/')[-1]+' extracted successfully')
                    except Exception as e:
                        log('[  WARN  ] Unable to extract file ' +file.split('/')[-1])
                        self.throwWarningSignal.emit("SomePythonThings Zip Manager", 'Unable to extract file '+file.split('/')[-1]+"\n\nReason:\n"+str(e))
                        error = True
                    finally:
                        actualFile += 1
                else:
                    log(f"[   OK   ] Skipping file {file.text(0)}")
            self.updateProgressBar[int, int].emit(totalFiles, totalFiles)
            notify("Extraction Done!", "SomePythonThings Zip Manager has finished extracting the selected files and folders.", self.window)
            self.stopLoadingSignal.emit()
            if error:
                log('[  WARN  ] Zip file extracted with some errors')
                self.throwWarningSignal.emit("SomePythonThings Zip Manager", 'Zip file extracted with some errors')
            else:
                log('[   OK   ] Zip file extracted sucessfully')
                self.throwInfoSignal.emit("SomePythonThings Zip Manager", 'Zip file extracted sucessfully')
            openOnExplorer(directory, force=True)
        except Exception as e:
            if debugging:
                raise e
            self.stopLoadingSignal.emit()
            log('[ FAILED ] Error occurred while extracting zip File')
            self.throwErrorSignal.emit("SomePythonThings Zip Manager", 'Unable to extract the zip\n\nReason:\n'+str(e))



if(__name__=="__main__"):
    import __init__