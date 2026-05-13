import os
from PIL import Image

def generate_icons(png_path):
    if not os.path.exists(png_path):
        print(f"Error: {png_path} not found")
        return

    img = Image.open(png_path)
    
    # Generate ICO
    ico_path = 'assets/icon.ico'
    img.save(ico_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Generated {ico_path}")

    # Generate ICNS (macOS)
    # We create an iconset folder and then use iconutil
    if os.uname().sysname == 'Darwin':
        iconset_path = 'assets/icon.iconset'
        os.makedirs(iconset_path, exist_ok=True)
        
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        for size in sizes:
            # Standard resolution
            out = os.path.join(iconset_path, f'icon_{size}x{size}.png')
            img.resize((size, size), Image.Resampling.LANCZOS).save(out)
            
            # High resolution (@2x)
            if size <= 512:
                out_2x = os.path.join(iconset_path, f'icon_{size}x{size}@2x.png')
                img.resize((size*2, size*2), Image.Resampling.LANCZOS).save(out_2x)
        
        os.system(f'iconutil -c icns {iconset_path}')
        os.system(f'rm -rf {iconset_path}')
        print(f"Generated assets/icon.icns")
    else:
        print("Skipping ICNS generation (not on macOS)")

if __name__ == "__main__":
    generate_icons('assets/sorterr_icon.png')
