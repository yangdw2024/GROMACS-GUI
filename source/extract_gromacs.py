import os
import pyunpack


def main():
    os.chdir("D:\\YDW\\Trae_Gromacs")
    pyunpack.Archive("gromacs.rar").extractall("D:\\YDW\\Trae_Gromacs")
    print("Extraction completed!")


if __name__ == "__main__":
    main()
