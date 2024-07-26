#/usr/bin/python3
from rich import console
from rich.table import Table
from rich.panel import Panel
import re, requests
import os
import subprocess
import shutil
import sys


def get_glibc_list():
    common_url = 'https://mirror.tuna.tsinghua.edu.cn/ubuntu/pool/main/g/glibc/'
    # url = 'http://archive.ubuntu.com/ubuntu/pool/main/g/glibc/'
    old_url = 'http://old-releases.ubuntu.com/ubuntu/pool/main/g/glibc/'
    
    archs = ["amd64", "i386"]
    
    result = []
    content = str(requests.get(common_url).content)
    content_old = str(requests.get(old_url).content)
    for arch in archs:
        for _ in re.findall('libc6_(2\\.[0-9][0-9]-[0-9]ubuntu[0-9\\.]*_{}).deb'.format(arch), content):
            result.append((_, "normal"))
        for _ in re.findall('libc6_(2\\.[0-9][0-9]-[0-9]ubuntu[0-9\\.]*_{}).deb'.format(arch), content_old):
            result.append((_, "old"))
    result = sorted(set(result), key=result.index)
    result.sort()
    return result


def strings(file, min_length=4) :
    with open(file, 'rb') as f:
        content = f.read()
    pattern = rb'[\x20-\x7E]{' + str(min_length).encode() + rb',}'
    strings = re.findall(pattern, content)
    strings = [s.decode('utf-8', errors='ignore') for s in strings]
    return strings

console = console.Console()


def libc_table(libc_list: list):
    table = Table()
    table.add_column("index")
    table.add_column("libc version")

    for i in range(len(libc_list)):
        content = f"[green]{libc_list[i][0]}"
        if libc_list[i][1] == "old":
            content += f"[red]\\[old]"
        table.add_row(f"[red]{i + 1:#3}", content)

    return table

def get_libc_version(libc_path):
    for s in strings(libc_path):
        if "ubuntu" in s:
            fd = re.findall(r"Ubuntu GLIBC (.*)\)", s)
            if len(fd):
                return fd[0]
    return None


def extract_major_minor_version(version_string):
    """
    提取版本字符串中的主版本号和次版本号。
    
    :param version_string: 版本字符串
    :return: (主版本号, 次版本号) 的元组
    """
    match = re.match(r"(\d+\.\d+)", version_string)
    if match:
        return match.group(1)
    return None

def find_matching_versions(target_version, version_list):
    """
    从版本列表中找到所有与目标版本匹配的项（主版本号和次版本号）。
    
    :param target_version: 目标版本字符串
    :param version_list: 版本字符串列表
    :return: 匹配的项列表
    """
    target_major_minor_version = extract_major_minor_version(target_version)
    if target_major_minor_version is None:
        return []

    matching_versions = [version for version in version_list if extract_major_minor_version(version[0]) == target_major_minor_version]
    return matching_versions

def copy_directory_contents(src_dir, dest_dir):
    # 确保目标目录存在
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    for item in os.listdir(src_dir):
        src_path = os.path.join(src_dir, item)
        dest_path = os.path.join(dest_dir, item)
        
        if os.path.isdir(src_path):
            # 如果是目录，递归拷贝子目录
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        else:
            # 如果是文件，拷贝文件
            shutil.copy2(src_path, dest_path)

def run_system_command(command, cwd):
    result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr

def extract_library_names(input_string):
    lines = input_string.split('\n')
    libraries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if '=>' in line:
            parts = line.split('=>')
            # 提取 '=>' 左边的库名称
            left_part = parts[0].strip()
            tp = []
            match = re.search(r'(\S+)', left_part)
            if match:
                tp.append(match.group(1))
            else:
                continue
            # 提取 '=>' 右边的库名称
            right_part = parts[1].strip()
            match = re.search(r'(\S+)', right_part)
            if match:
                tp.append(match.group(1))
            else:
                continue
            libraries.append(tp)
        else:
            # 提取单个库名称
            match = re.search(r'(\S+)', line)
            if match:
                libraries.append([match.group(1)])

    return libraries

def patch_libc(version: tuple, elf_path: str):
    console.print(f"[green][+] start patching...")
    abspath = os.path.abspath(elf_path)
    result = run_system_command(f"ldd {abspath}", "./")[1]
    libs = extract_library_names(result)
    
    for lib in libs:
        original_lib = ""
        sx = re.search(r'/([^/]+)$', lib[0])
        if sx:
            lib_name = sx.group(1)
        else:
            lib_name = lib[0]
        original_lib = lib[0]
        if "linux-vdso" in lib_name:
            # linux-vdso skip
            continue
        elif "ld-linux" in lib_name or "ld" in lib_name: 
            # find ld
            ld_path = None
            for p in os.listdir(f"./libs/{version[0]}/"):
                if "ld-" in p:
                    ld_path = os.path.abspath(f"./libs/{version[0]}/{p}")
                    break
            if ld_path == None:
                assert("can't find ld.so")
            console.print(f"[green][+] [blue]patchelf [yellow][b]{lib_name} => {ld_path}")
            run_system_command(f"patchelf --set-interpreter {ld_path} {abspath}", "./")
        elif lib_name == "libc.so.6":
            libc_path = None
            for p in os.listdir(f"./libs/{version[0]}/"):
                if "libc-" in p or p == "libc.so.6":
                    libc_path = os.path.abspath(f"./libs/{version[0]}/{p}")
                    break
            if libc_path == None:
                assert("can't find libc.so")
            console.print(f"[green][+] [blue]patchelf [yellow][b]{original_lib} => {libc_path}")
            run_system_command(f"patchelf --replace-needed {original_lib} {libc_path} {abspath}", "./")
        else:
            # 普通库 这里可能容易出问题, 报错了发 issue
            lib_name_without_so = lib_name.split(".so")[0]
            lib_name_without_so = lib_name_without_so.split("-")[0]
            lib_path = None
            for p in os.listdir(f"./libs/{version[0]}/"):
                if lib_name_without_so in p:
                    lib_path = os.path.abspath(f"./libs/{version[0]}/{p}")
                    break
            if lib_path != None:
                console.print(f"[green][+] [blue]patchelf [yellow][b]{original_lib} => {lib_path}")
                run_system_command(f"patchelf --replace-needed {original_lib} {lib_path} {abspath}", "./")
    console.print(f"[green][+] finished patching")
                

def download_libc(version: tuple):
    
    if os.path.exists(f"./libs/{version[0]}"):
        console.print(f"[yellow][+] [b]{version[0]} already exists. skip download")
        return
    
    if version[1] == "old":
        download_url = f'http://old-releases.ubuntu.com/ubuntu/pool/main/g/glibc/libc6_{version[0]}.deb'
    else:
        download_url = f'https://mirror.tuna.tsinghua.edu.cn/ubuntu/pool/main/g/glibc/libc6_{version[0]}.deb'
    
    # 删除 tmp 目录下所有文件
    for filename in os.listdir("./tmp/"):
        file_path = os.path.join("./tmp/", filename)
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)  # 删除文件或符号链接
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)  # 删除目录及其内容
    
    # 开始下载
    console.print(f"[green][+] downloading [red][b]{version[0]}")
    with open(f"tmp/{version[0]}.deb", "wb") as f:
        f.write(requests.get(download_url, stream=True).content)
        f.close()
    console.print(f"[green][+] finished")
    
    # 解压开始
    run_system_command(f"ar xv {version[0]}.deb", "./tmp/")
    
    if os.path.exists(f"data.tar.zst"):
        run_system_command("tar -I zstd -xf data.tar.*", "./tmp/")
    else:
        run_system_command("tar xf data.tar.*", "./tmp/")
    console.print(f"[green][+] [red][b]{version[0]}.deb [green]extracted.")
    
    if os.path.exists(f"./tmp/lib/"):
        copy_directory_contents(f'./tmp/lib/{os.listdir("./tmp/lib/")[0]}', f"./libs/{version[0]}")
    elif os.path.exists(f"./tmp/usr/lib/"):
        copy_directory_contents(f'./tmp/usr/lib/{os.listdir("./tmp/usr/lib/")[0]}', f"./libs/{version[0]}")
    else:
        assert("can't find extracted lib directory")
    
    
def init():
    if not os.path.exists("libs"):
        os.makedirs("libs")
    if not os.path.exists("tmp"):
        os.makedirs("tmp")

def main(libc_path, elf_path, mode):
    init()

    if mode == "libc":
        libc_version = get_libc_version(libc_path)
        if libc_version != None:
            console.print(f"[green][+] libc version: [red][b]{libc_version}")
        else:
            console.print(f"[red][-] [b]can't find libc version from libc.so.6")
            exit()

        libc_list = get_glibc_list()
        closest_match = find_matching_versions(libc_version, libc_list)
        console.print(f"[green][+] relevant matches: ", libc_table(closest_match))
        choice = console.input(f"[blue][+] please choice: ")
        while not choice.isnumeric() or not(1 <= int(choice) <= len(closest_match)):
            console.print(f"[red][-] [b]invalid choice")
            choice = console.input(f"[blue][+] please choice: ")
        choiced = closest_match[int(choice) - 1]
        console.print(f"[green][+] your choice: [red][b]{choiced[0]}")
        download_libc(choiced)
        patch_libc(choiced, elf_path)
        console.print(f"[green][+] [blue]done")
    else:
        libc_list = get_glibc_list()
        console.print(f"[green][+] libc list: ", libc_table(libc_list))
        choice = console.input(f"[blue][+] please choice: ")
        while not choice.isnumeric() or not(1 <= int(choice) <= len(libc_list)):
            console.print(f"[red][-] [b]invalid choice")
            choice = console.input(f"[blue][+] please choice: ")
        choiced = libc_list[int(choice) - 1]
        console.print(f"[green][+] your choice: [red][b]{choiced[0]}")
        download_libc(choiced)
        patch_libc(choiced, elf_path)
        console.print(f"[green][+] [blue]done")
def print_help():
    help_t = [
        "[red] libc mode:",
        "[green] python3 [red]autopatch.py [yellow]libc \\[libc file path] \\[elf path]\n",
        "[red] elf mode:",
        "[green] python3 [red]autopatch.py [yellow]elf \\[elf path]\n",
        "\t[yellow]\\[libc file path] [green]Point to your libc file address, such as libc.so.6",
        "\t[yellow]\\[elf path] [green]Point to your elf file address, such as pwn\n",
        "[purple] example command: \n\tpython3 autopatch.py libc libc.so.6 pwn",
        "[purple] \tpython3 autopatch.py elf pwn\n",
        "[blue]If you choose libc mode, the program will automatically retrieve the corresponding libc version from the provided libc file, match libc files with similar versions from the libc library, and then use patchelf to automatically patch the elf file to the same libc version as the provided libc file.\n",
        "[blue]But if you are using elf mode, the program will print all libc versions, and you need to choose one to patch."
    ]
    console.print(Panel("\n".join(help_t), title="AutoELFPatcher b1.0 - help"))

if __name__ == "__main__":
    try:
        args = sys.argv
        if len(args) < 2:
            console.print(f"[red][-] [b]usage: python3 autopatch.py args.. please check help --help")
            exit()
        if args[1] == "--help" or args[1] == "-h" or args[1] == "help":
            print_help()
            exit()
        if len(args) == 4 and args[1] == "libc":
            libc_path = args[2]
            elf_path = args[3]
            main(libc_path, elf_path, "libc")
        elif len(args) == 3 and args[1] == "elf":
            elf_path = args[2]
            main(None, elf_path, "elf")
        else:
            console.print(f"[red][-] [b]usage: python3 autopatch.py args.. please check help --help")
            exit()
        # main()
    except Exception as e:
        console.print_exception(show_locals=True)