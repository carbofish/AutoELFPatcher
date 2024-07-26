# AutoELFPatcher
A glibc auto patching tool prepared for pwner

Retrieve libc list, download and decompress operation from [glibc-all-in-one](https://github.com/matrix1001/glibc-all-in-one)

To use this script, you need to install [patchelf](https://github.com/NixOS/patchelf)

# Usage
*libc mode*

![libc_mode](https://github.com/carbofish/AutoELFPatcher/raw/main/assets/patch.gif)

*elf mode*

![libc_mode](https://github.com/carbofish/AutoELFPatcher/raw/main/assets/patch_elf.gif)

## AutoELFPatcher b1.0 - help

libc mode:
python3 autopatch.py libc [libc file path] [elf path]

elf mode:
python3 autopatch.py elf [elf path]

       [libc file path] Point to your libc file address, such as libc.so.6
       [elf path] Point to your elf file address, such as pwn

example command:
       python3 autopatch.py libc libc.so.6 pwn
       python3 autopatch.py elf pwn

If you choose libc mode, the program will automatically retrieve the corresponding libc version from the
provided libc file, match libc files with similar versions from the libc library, and then use patchelf
to automatically patch the elf file to the same libc version as the provided libc file.

But if you are using elf mode, the program will print all libc versions, and you need to choose one to 
patch.                                                                                                   