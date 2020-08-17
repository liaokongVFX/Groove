from haishoku.haishoku import Haishoku
from colorthief import ColorThief


def getDominantColor(imagePath, resType=str):
    """ 获取指定图片的主色调

    Parameters
    ----------
    imagePath : 图片路径\n
    reType : 返回类型，str返回十六进制字符串，否则为rgb元组
    """
    colorThief = ColorThief(imagePath)
    r, g, b = colorThief.get_color()
    # 如果颜色太浅就使用默认主题色
    if r > 170 and g > 170 and b > 170:
        cond_1 = abs(r - g) <= 25 and abs(r - b) <= 25 and abs(g - b) <= 25
        cond_2 = (r > 220 and g > 220 and b > 200) or (
            (r > 200 and g > 220 and b > 220)) or (r > 220 and g > 200 and b > 200)
        if cond_1 or cond_2:
            #r, g, b = 103, 108, 136
            r, g, b = 12, 60, 94
    if resType is str:
        rgb = hex(r)[2:].rjust(2, '0') + \
            hex(g)[2:].rjust(2, '0') + hex(b)[2:].rjust(2, '0')
    else:
        rgb = (r, g, b)
    return rgb


if __name__ == "__main__":
    rgb = getDominantColor(
        r"D:\Python_Study\Groove\resource\Album_Cover\(un)sentimental spica\(un)sentimental spica.jpg")
    print(rgb)