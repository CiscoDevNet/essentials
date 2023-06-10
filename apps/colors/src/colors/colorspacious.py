import numpy as np
from colorspacious import cspace_convert

def hex_to_rgb(hex_color):
    return [int(hex_color[i:i+2], 16) for i in (1, 3, 5)]  # Skip the '#'

def rgb_to_lab(rgb):
    # Normalize RGB values to the range [0, 1]
    rgb = np.array(rgb) / 255.0

    # Convert RGB to CIELab
    lab = cspace_convert(rgb, "sRGB1", "CIELab")

    return lab

def find_closest_color(target_hex, colors):
    target_rgb = hex_to_rgb(target_hex)
    target_lab = rgb_to_lab(target_rgb)

    min_distance = float('inf')
    closest_color = None

    for color_hex in colors:
        color_rgb = hex_to_rgb(color_hex)
        color_lab = rgb_to_lab(color_rgb)

        distance = np.linalg.norm(target_lab - color_lab)

        if distance < min_distance:
            min_distance = distance
            closest_color = color_hex

    if isinstance(colors, dict):
        return colors.get(closest_color)

    return closest_color
