import io
from PIL import Image
import base64

def get_image_by_dalle(client, genre, img_prompt):
    response = client.images.generate(
        model = 'dall-e-3',
        prompt = 'the name of this story is' + genre + ' ' + img_prompt + "The style is 3D computer-rendered children's movie animation with vibrant colors adn detailed textures",
        size = "1024x1024",
        quality = "standard",
        n=1,
        response_format = 'b64_json' # binary data를 text format으로 incoding (저장 및 전송 용이)
    )

    image_data = base64.b64decode(response.data[0].b64_json) #text format을 다시 binary data로 decoding
    image = Image.open(io.BytesIO(image_data))  # io.BytesIO는 메모리에 있는 바이너리 데이터를 파일처럼 읽을수 있음.
    #PIL(pillow) 라이브러리의 Image.open 매서드로 이미지를 열고 이미지 객체 생성 (io.BytesIo 객체 문빤하이나, 파일경로도 받을수 있음.)

    # 이미지 확인 및 저장
    # image.show()  # 이미지 보기
    # image.save("output_image.png")  # 파일로 저장
    return image