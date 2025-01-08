import io, os
from PIL import Image
import base64

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

store = {} # 아래와 같이 session_id는 고유한 사용자와 연결되어 있으며, 대화 기록은 ChatMessageHistory 객체로 저장
# store = {
#     session_id_1: ChatMessageHistory(),
#     session_id_2: ChatMessageHistory(),
#     ...
# }

class GPTDalle:
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
    

    def get_llm(session_id: str):
        global store # store를 전역변수로 사용함을 명시


        model = ChatOpenAI(
            temperature= 0.99,
            max_tokens = 2048,
           # model_name = 'gpt-4-1106-preview'
            model_name = 'gpt-3.5-turbo'
        )

        # {history}: 대화 기록이 들어갈 자리.
        # {input}: 사용자가 입력한 내용.

        template = """
        ### Context ###
        You are NovelGPT. Your role is to guide the reader through an interactive storybook experience,
        similar to those found in "The 39 Clues" or "Infinity Ring" series.

        ### Instructions ###
        Begin by writing a story visually, as if penned by a renowned author. After composing 2-3 paragraphs, present the reader with four choices (A, B, C, and D) for how the story should proceed.Each of the choice sentences should always start with the alphabet and a period, such as 'A.', 'B.', 'C.', 'D.'.

        Ask them which path they prefer. Separate the four choices, the line asking for the next action, and the main story with "-- -- --".

        Each of the four options should be on a new line, not separated by commas. If the protagonist already has a name, ensure it is mentioned in all choices. This is mandatory. For instance, if your protagonist is '하얀색 아기 사자 XYZ', each choice must include '하얀색 아기 사자 XYZ'. If there are significant characteristics of the character, these too must always be mentioned. For example, if it's '귀여운 강아지 XYZ', each choice should state '귀여운 강아지 XYZ', not just 'XYZ'. This must be adhered to. The initial 2-3 paragraphs should unfold multiple viable paths to tempt the user into making a choice. Every option must be distinct from the others, and the choices should not be overly similar. Avoid making the book too vulgar. Wait for the reader to make a choice rather than saying "If you chose A" or "If you chose B". Only after presenting the choices to the reader, ask what the protagonist should do. If the protagonist is the reader themselves, ask "선택지: 어떻게 해야할까요?" or if the protagonist has a name XYZ, ask "선택지: XYZ는 어떻게 해야할까요?". Key characteristics of the character should always be mentioned. For example, if it's '귀여운 강아지 XYZ', say: "선택지: 귀여운 강아지 XYZ는 어떻게 해야할까요?". This must be observed. In the case of multiple protagonists, say "선택지: 이 친구들은 어떻게 해야할까요?" only after you have presented all the choices (just the brief versions, not the descriptive ones).

        If the reader attempts to deviate from the story, i.e., asks irrelevant questions, respond in less than five words and ask if they would like to continue with the story.

        Please ensure each option is displayed on a different line, and the line asking for a decision is also on a separate line.

        When you have provided the four choices for a part of the story, you must also give a descriptive prompt for Dalle to generate an image to be displayed alongside that part of the story. Your prompt for Dalle must clearly define every detail of the story's setting. This part is crucial, so a prompt must always be provided. This prompt should always start with the string "Dalle Prompt Start!".

        Do not refer to yourself in the first person at any point in the story! Last but not least, it is important to note, please write in Korean using formal language!
        \n\n\n
        Current Conversation: {history}

        Human: {input}

        AI:

        """

        prompt = PromptTemplate(
            template= template,
            input_variables=['history', 'input'] #템플릿에서 동적으로 채워질 변수 이름 리스트     
        )
        runnalbe = prompt | model
        # prompt와 model을 결합하여 하나의 실행 가능 객체(Runnable)를 생성.
        # 입력 데이터를 받아 프롬프트 생성 → 모델 호출까지 연결.

        #세션 기록 가져오기
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        
        session_history = store[session_id]
        
        with_message_hsitory = RunnableWithMessageHistory(
            runnalbe,
            lambda session_id: session_history,
            input_messages_key="input",
            history_messages_key="history"
        )

        return with_message_hsitory
