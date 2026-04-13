from PIL import Image
import numpy as np
import sys
sys.path.append('d:/side_project/comic_tra/backend')
from typesetter import Typesetter

ts = Typesetter('C:/Windows/Fonts/msjh.ttc')
img_np = np.ones((200, 200, 3), dtype=np.uint8) * 255
img_pil = Image.fromarray(img_np)
res_img = ts.draw_text_in_box(img_pil, '測試微軟正黑體', (10, 10, 180, 180))
res_img.save('d:/side_project/comic_tra/backend/debug_output/test_msjh.jpg')
print('Typesetter tested successfully with msjh.ttc!')
