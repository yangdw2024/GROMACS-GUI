import os
import pyunpack

os.chdir("D:\\YDW\\Trae_Gromacs")
pyunpack.Archive("gromacs.rar").extractall("D:\\YDW\\Trae_Gromacs")
print("Extraction completed!")