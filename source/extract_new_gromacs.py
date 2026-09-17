import zipfile
import os


def main():
    zip_path = r"D:\YDW\Trae_Gromacs\gromacs-2026.1-plumed-CUDA.zip"
    extract_dir = r"D:\YDW\Trae_Gromacs\gromacs"

    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)

    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_dir)
        print(f"解压完成，共解压 {len(z.namelist())} 个文件")

    for item in os.listdir(extract_dir):
        item_path = os.path.join(extract_dir, item)
        if os.path.isdir(item_path):
            print(f"目录: {item}")


if __name__ == "__main__":
    main()
