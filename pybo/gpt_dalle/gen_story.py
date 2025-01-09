import streamlit as st, re
import uuid, os

from openai import OpenAI


from ..gpt_dalle.dalle_gpt import GPTDalle
from ..gpt_dalle.save_files import SaveFiles




#st.set_page_config(page_title='📚NovelGPT', layout ='wide',initial_sidebar_state='expanded')

################기능 구현 함수#####################

#[시작] 버튼 또는  [진행하기] 버튼을 클릭하면 실행되는 함수
#_pos = st.empty
# @st.cache_data(show_spinner='Generating your story...')
# def get_output(_pos=None, oid='', genre=''):
#     # _pos가 None일 경우 st.empty()로 초기화
#     # if _pos is None:
#     _pos = st.empty()

#     if oid:
#         #선택지를 클릭하는 순간 직전 과거의 스토리와 선택지의 상태값을 변경
#         st.session_state['genreBox_state'] = True
#         st.session_state[f'expanded_{oid}'] = False # 스토리
#         st.session_state[f'radio_{oid}_disabled'] = True # 라디오버튼
#         st.session_state[f'submit_{oid}_disabled'] = True # 진행하기버튼

#         # 방금 선택한 선택지에서 값을 저장

#         user_choice = st.session_state[f'radio_{oid}']
    
#     if genre:
#         st.session_state['genreBox_state'] = False
#         user_choice = genre

#     with _pos:
#         #사용자의 선택지로부터 스토리오 이미지를 받아냄
#         data = get_story_and_image(genre, user_choice)
#         add_new_data(data['story'], data['decisionQuestion'], data['choices'], data['dalle_img'])

class GenerateStory:

    @staticmethod
    def auth():
        with open("C:/projects/api_keys/api_keys.txt") as f:
            file = f.read()
        match = re.search(r"OPENAI_API_KEY = '(.*?)'", file)
        if match:
            os.environ['OPENAI_API_KEY'] = match.group(1)
            print("API Key Loaded.")

   

    @staticmethod
    def is_korean(text):
        # 한글 문자가 포함되어 있으면 True 반환
        return bool(re.search(r'[\uac00-\ud7af]', text))

    @staticmethod
    def get_story_and_image(genre, user_choice, client):
        llm_model = GPTDalle.get_llm('test')

        # LLM으로부터 응답받기
        llm_generation_result = llm_model.invoke(
            {"input": user_choice},
            config={
                "configurable": {"session_id": "test"}
            }
        ).content

        response_list = llm_generation_result.split('\n')

        # 이미지 프롬프트 추출
        if len(response_list) > 1:
            img_prompt = response_list[-1]
            dalle_img = GPTDalle.get_image_by_dalle(client, genre, img_prompt)
        else:
            img_prompt = ""
            dalle_img = None

        # 필터링하여 응답 리스트 정리
        responses = list(filter(lambda x: x != '' and x != '-- -- --', response_list))
        responses = list(filter(lambda x: 'Dalle Prompt' not in x and 'Image prompt' not in x, responses))
        responses = [s.strip() for s in responses if s.strip()]

        print("response: ", responses)

        # 초기화
        story_en = []
        story_kr = []
        choices_en = []
        choices_kr = []
        decision_question_en = ""
        decision_question_kr = ""

        is_choice_section = False

        # 응답 처리
        for response in responses:
            if response.startswith("선택지:"):
                decision_question_kr = '**' + response + '**'
            elif response.lower().startswith(("a.", "b.", "c.", "d.")):
                # 선택지 부분인 경우
                if GenerateStory.is_korean(response):  # 한국어 선택지
                    choices_kr.append(response)
                else:  # 영어 선택지
                    choices_en.append(response)
                    is_choice_section = True
            elif GenerateStory.is_korean(response):  # 한국어 문장으로 판단
                story_kr.append(response)
            else:  # 영어 문장으로 간주
                story_en.append(response)

        # 이미지 프롬프트가 포함된 경우 제거
        story_en = [line.replace(img_prompt, '').strip() for line in story_en]
        story_kr = [line.replace(img_prompt, '').strip() for line in story_kr]

        print('choices_en : ', choices_en, '\n', 'choices_kr: ', choices_kr)

        return {
            'story_en': "\n".join(story_en),
            'story_kr': "\n".join(story_kr),
            'choices_en': choices_en,
            'choices_kr': choices_kr,
            'decisionQuestion_en': decision_question_en,
            'decisionQuestion_kr': decision_question_kr,
            'dalle_img': dalle_img
        }


    # def get_story_and_image(genre, user_choice, client):
    #     # client = OpenAI() 
    #     # # API Key
    #     # GenerateStory.auth()
    #     llm_model = GPTDalle.get_llm('test')

    #     # 사용자의 선택지인 user_choice로부터 LLM이 작성한 다음 스토리, 다음 선택지 4개, Dalle 프롬프트를 전달받습니다.
    #     llm_generation_result = llm_model.invoke(
    #         {"input" : user_choice },
    #         config={
    #             "configurable" : {"session_id": "test"}
    #         }
    #     ).content

    #     # 줄바꿈 기준으로 위의 llm_generation_result를 문자열 리스트로 변환. 이렇게 되면 마지막 줄은 Dalle Prompt이다.
    #     # ex) [스토리 문장1, 스토리 문장2, -- -- --, A선택지, B선택지, C선택지, D선택지, -- -- --, 달리 프롬프트]
    #     response_list = llm_generation_result.split('\n')

    #     if len(response_list) !=1:
    #         #문자열 리스트에서 마지막 원소를 추출하면 달리 프롬프트
    #         img_prompt = response_list[-1]
    #         dalle_img = GPTDalle.get_image_by_dalle(client, genre, img_prompt)
        
    #     else:
    #         dalle_img = None
        
    #     # choices = []
    #     # story =''
    #     # decisionQuestion = ''  # 기본값으로 초기화

    #     #메인스토리(story), 질문(decisionQuestion), 선택지(choices)만 responses의 원소로 남김
    #     responses = list(filter(lambda x: x != '' and x != '-- -- --',response_list))
    #     responses = list(filter(lambda x: 'Dalle Prompt' not in x and 'Image prompt' not in x, responses))
    #     responses = [s for s in responses if s.strip()]

    #     print("response: " ,responses)

    #     story_en = []
    #     story_kr = []
    #     choices_en = []
    #     choices_kr = []
    #     decision_question_en = ""
    #     decision_question_kr = ""

    #     # Process responses to separate English and Korean parts
    #     is_choice_section = False


    #     # #메인스토리(story), 질물(decisionQuestion), 선택지(chices)를 파싱하여 각각 저장
    #     # for response in responses:
    #     #     # 화면에 출력할 선택지 질문에 양 옆에 **를 붙여서 decisionQuestion에 저장.
    #     #     # ex) **선택지: 아기 펭귄 보물이는 어떻게 해야할까요?'**

    #     #     if response.startswith('선택지:'):
    #     #         decisionQuestion = '**' + response + '**'
            
    #     #     elif response[1] == '.':
    #     #         # 4개의 선택지를 choices라는 문자열 리스트에 저장
    #     #         choices.append(response)
    #     #     # 질문(decisionQuestion)과 선택지(choices)를 제외하면 메인 스토리이므로, story에 저장
    #     #     else:
    #     #         story += response +'\n'

    #     for response in responses:
    #         if response.startswith("선택지:"):
    #             decision_question_kr = '**' + response + '**'
    #         elif response.lower().startswith("a.") or response.lower().startswith("b.") or \
    #             response.lower().startswith("c.") or response.lower().startswith("d."):
    #             if is_choice_section:  # If choice section for Korean
    #                 choices_kr.append(response)
    #             else:  # If choice section for English
    #                 choices_en.append(response)
    #                 is_choice_section = True
    #         elif any(c.isalpha() and c.islower() for c in response):  # Simple heuristic for English
    #             story_en.append(response)
    #         else:  # Assume the rest is Korean
    #             story_kr.append(response)
            
    #     # #스토리에 dalle prompt가 여전히 남아있을 경우 제거
    #     # story_en = story_en.replace(img_prompt, '')
    #     # story_kr = story_kr.replace(img_prompt, '')

    #     #  # 만약 decisionQuestion이 여전히 빈 값이라면 기본값을 설정
    #     # if not decisionQuestion:
    #     #     decisionQuestion = '**다음 선택지는 무엇일까요?**'

    #     print('choices_en : ' ,choices_en, '\n',
    #             'choices_kr: ', choices_kr)
    #     return {
    #             'story_en': "\n".join(story_en),
    #             'story_kr': "\n".join(story_kr),
    #             'choices_en': choices_en,
    #             'choices_kr': choices_kr,
    #             'decisionQuestion_en': decision_question_en,
    #             'decisionQuestion_kr': decision_question_kr,
    #             'dalle_img': dalle_img
    #         }

        # return {
        #     'story' : story, # 화면에 출력한 스토리
        #     'decisionQuestion' : decisionQuestion, # 화면에 출력할 질문. ' 다음은 어떻게 할까요?'
        #     'choices' : choices, # 화면에 출력할 실제 4개의 선택지
        #     'dalle_img' : dalle_img # 화면에 출력할 dalle이미지
        # }

    #스토리, 질문, 선택지, 이미지를 저장하는 함수
    @staticmethod
    def add_new_data(*data):
        # uuid.uuid4() 코드를 활용하여 임의의 난수를 생성합니다.
        # ex) oid = fd5198c7-67a5-4fc9-83ad-56afc16e2d6a
        oid = str(uuid.uuid4())
        # 새로운 part의 oid 값을 이전 part의 oid 값들이 저장되어져 있는 리스트에 누적하여 저장합니다.   
        st.session_state['oid_list'].append(oid)

        #data_dict에 oid를  key 값으로 현재 part의 데이터를 저장
        st.session_state['data_dict'][oid] = data

    #화면에 각 Part를 출력하는 함수

    # @staticmethod
    # def generate_content(story, decisionQuestion, choices: list, img, oid):
    #     #과거에 출력된 적이 있던 oid(part/스토리는) get_output() 함수의 첫 조건문에서 st_session_state에 기록되었기 때문에 실행되지 않음
    #     if f'expanded_{oid}' not in st.session_state:
    #         st.session_state[f'expanded_{oid}'] = True # 새로운 스토릴르 펼치기 위한 값
    #     if f'radio_{oid}_disabled' not in st.session_state:
    #         st.session_state[f'radio_{oid}_disabled'] = False # 4개의 선택지를 선택하는 라디오 버튼을 열기 위한 값
    #     if f'submit_{oid}_disabled' not in st.session_state:
    #         st.session_state[f'submit_{oid}_disabled'] = False # 진행하기 버튼을 열기 위한 값
        
    #     #화면에 각 스토리 파트가 출력될때, 'Part 숫자'에서의 숫자를 계산하는 코드이며, 숫자는 1씩 증가
    #     story_pt = list(st.session_state['data_dict'].keys()).index(oid) + 1

    #     #각 스토리는 'Part 숫자'형태로 화면에 출력되며 각 part는 expanded_{oid}의 값에 따라 열리거나 닫힘
    #     expander = st.expander(f'Part {story_pt}', expanded=st.session_state[f'expanded_{oid}'])
    #     col1, col2 = expander.columns([0.65, 0.35])
    #     empty = st.empty


    #     #col2는 스토리 진행중에 표시될 우측 화면을 의미합니다. 우측 화면에 dalle가 생성한 이미지를 표현합니다.
    #     if img:
    #         #col2.image(img, width=40, use_column_width='always')
    #         col2.image(img, width=40, use_container_width=True)
        
    #     # col1은 스토리 진행중에  표시될 좌측 화면을 의미
    #     with col1:
    #         st.write(story)
        
    #         if decisionQuestion and choices:
    #             with st.form(key=f'user_choice_{oid}'):
    #                 st.radio(decisionQuestion, choices, disabled=st.session_state[f'radio_{oid}_disabled'], key=f'radio_{oid}')
    #                 # 진행하기 버튼을 클릭하면 get_output 함수가 실행
    #                 # 만약, 이미 진행되던 part라면 disabled 값이 true가 되어 진행하기 버튼을 활성화됨.
    #                 st.form_submit_button(
    #                     label = "진행하기",
    #                     disabled=st.session_state[f'submit_{oid}_disabled'],
    #                     on_click=GenerateStory.get_output, 
    #                     args=[empty], 
    #                     kwargs={'oid':oid}
    #                 )
    #     GenerateStory.add_buttons(story, decisionQuestion, choices)

    # Streamlit UI에 버튼 추가
    @staticmethod
    def add_buttons(story, decisionQuestion, choices):
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("Save as PDF"):
                file_path = SaveFiles.save_as_pdf(story, decisionQuestion, choices)
                st.success(f"PDF saved successfully: {file_path}")

        with col2:
            if st.button("Save as Word"):
                file_path = SaveFiles.save_as_word(story, decisionQuestion, choices)
                st.success(f"Word document saved successfully: {file_path}")

        with col3:
            if st.button("Save as Excel"):
                file_path = SaveFiles.save_as_excel(story, decisionQuestion, choices)
                st.success(f"Excel file saved successfully: {file_path}")

        with col4:
            if st.button("Save as Image"):
                file_path = SaveFiles.save_as_image(story, decisionQuestion, choices)
                st.success(f"Image saved successfully: {file_path}")

        with col5:
            if st.button("Save as HTML"):
                file_path = SaveFiles.save_as_html(story, decisionQuestion, choices)
                st.success(f"HTML saved successfully: {file_path}")

# ##### 메인 함수 ###########

# def main():
#     #기본 페이지 설정
#     st.title(f"📚 NovelGPT")

#     #스토리 전개 시 각 part의 데이터를 저장할 리스트
#     if 'data_dict' not in st.session_state:
#         st.session_state['data_dict']  = {}
    
#     #문자열 난수를 저장할 문자열 리스트. 스토리 전개 시 각각의 난수는 각 Part의 Key값 역할을 하게됨.
#     if 'oid_list' not in st.session_state:
#         st.session_state['oid_list'] = []

#    # 사용자가 OpenAI API Key 값을 작성하면 저장되는 저장될 변수.
#     # if 'openai_api_key' not in st.session_state:
#     #     st.session_state['openai_api_key'] = ''
   
#    # 사용자가 OpenAI API Key 값을 작성하는 칸의 활성화 여부. OpenAI Key 값이 입력되기 전에는 칸이 활성화(False) 

#     if 'apiBox_state' not in st.session_state:
#         st.session_state['apiBox_state'] = False

#    # 사용자가 첫 시작 시 주인공 또는 줄거리를 작성하면 저장될 변수. 기본 값은 '아기 펭귄 보물이의 모험'이다.
#     if 'genre_input' not in st.session_state:
#         st.session_state['genre_input'] = 'David의 꿈을 찾아서'
    
#    # 사용자가 첫 시작 시 주인공 또는 줄거리를 작성하는 칸의 활성화 여부. OpenAI Key 값이 입력되기 전에는 칸이 비활성화(True)    
#     if 'genreBox_state' not in st.session_state:
#         st.session_state['genreBox_state'] = False
   
#    #OpenAO API Key 인증하는 함수
#     def auth():
#         with open("C:/projects/api_keys/api_keys.txt") as f:
#             file = f.read()
#         match = re.search(r"OPENAI_API_KEY = '(.*?)'", file)
#         if match:
#             os.environ['OPENAI_API_KEY'] = match.group(1)
#             print("API Key Loaded.")
#         # os.environ['OPEN_API_KEY'] = st.session_state.openai_api_key
#         # st.session_state.genreBox_state = False

#         # # API를 입력 칸[]의 상태를 반영한느 변수입니다. API KEY를 입력(SUBMIT 버튼을 클릭)하면 해당 칸은 비활성화(True)
#         # st.session_state.apiBox_state =True
#     auth()

#     # 좌측의 사이트바 UI
#     # with st.sidebar:
#     #     st.header('📚 아이스기술 GPT')

#     #     st.markdown('''
#     #     NovelGPT는 소설을 작성하는 인공지능입니다. GPT-4와 Dalle를 사용하여 스토리가 진행됩니다.
#     #     ''')
        
#     #     st.info('**Note:** OpenAI API Key를 입력하세요.')

#         #OpenAI Key 값을 입력하는칸
#         # with st.form(key='API Keys'):
#         #     openai_key = st.text_input(
#         #         label = 'OpenAI API Key',
#         #         key='openai_api_key',
#         #         type='password', 
#         #         disabled= st.session_state.apiBox_state, # 비활성 여부 변수로 apiBox_state를 사용
#         #         help = 'OpenAI API key은 https://platform.openai.com/account/api-keys 에서 발급 가능합니다.',
#         #     )

#         #     btn = st.form_submit_button(label='Submit', on_click=auth)
        
#         # with st.expander('사용 가이드'):
#         #     st.markdown('''
#         #     - 위의 입력 칸에 <OpenAI API Key>를 작성 후 [Submit] 버튼을 누르세요. 
#         #     - 그 후 우측 화면에 주제나 주인공에 대한 서술을 묘사하고 [시작!] 버튼을 누르세요.
#         #     - 스토리가 시작되면 선택지를 누르며 내용을 전개합니다.
#         #     ''')        

#         # with st.expander('더 많은 예시 보러가기'):
#         #     st.write('GPT API 활용법')
    
#     # 시작 시 openai api key값이 입력되지 않을 경우 경고문구 출력
#     # if not openai_key.startswith('sk-'):
#     #     st.warning('OpenAI API key가 입력되지 않았습니다.', icon='⚠')
    
#     #Genre Inpup widget
#     with st.container():
#     # 5개의 버튼 추가 (반응형)
        

#         # 입력 필드와 버튼 배치
#         col_1, col_2, col_3 = st.columns([8, 1, 1], gap='small')

#         col_1.text_input(
#             label='Enter the theme/genre of your story',
#             key='genre_input',
#             placeholder='Enter the theme of which you want the story to be',
#             disabled=st.session_state.genreBox_state
#         )

#         col_2.write("")
#         col_2.write("")
#         col_2_cols = col_2.columns([0.5, 6, 0.5])
#         col_2_cols[1].button(
#             ':arrows_counterclockwise: &nbsp; Clear',
#             key='clear_btn',
#             on_click=lambda: setattr(st.session_state, "genre_input", ''),
#             disabled=st.session_state.genreBox_state
#         )

#         col_3.write('')
#         col_3.write('')
#         # 처음 시작! 버튼을 클릭하면 get_output 함수가 실행
#         begin = col_3.button(
#             '시작!',
#             on_click=get_output, args=[st.empty()], kwargs={'genre': st.session_state.genre_input},
#             disabled=st.session_state.genreBox_state
#         )

#         # 각 파트를 순서대로 출력
#         for oid in st.session_state['oid_list']:
#             data = st.session_state['data_dict'][oid]
#             story = data[0]
#             decisionQuestion = data[1]
#             choices = data[2]
#             img = data[3]

#             # 각 스토리를 출력하는 함수
#             generate_content(story, decisionQuestion, choices, img, oid)

        
       


# if __name__=="__main__":
#     main()
    

