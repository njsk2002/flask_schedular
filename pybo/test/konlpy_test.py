import pandas as pd
import openpyxl    
import konlpy
import json
import re
from konlpy.tag import Okt
from collections import Counter
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from wordcloud import wordcloud



filename = 'A000020_동화약품 테마 주식.csv'
inputFileName = 'C:/projects/blogdata/rowdata/' + filename 

data =pd.read_csv(inputFileName)

data_add = ''

for index, column in enumerate(data.columns):
    if index == 1:  # 두 번째 열 선택
        second_column = data[column]
        data_add += ' '.join(second_column)  # 두 번째 열 데이터를 문자열로 결합


# # 두 번째 열의 데이터를 리스트로 변환하여 결합
# data_add = ' '.join([str(item) for item in data.iloc[:, 1]])

#print(data_add)
        
# 품사중 명사만 추출
nlp = Okt()

data_N = nlp.nouns(data_add)

#print(data_N)

count = Counter(data_N)
#print(count)

word_count = dict()
for tag, counts in count.most_common(200):
    if(len(str(tag))>1):
        word_count[tag] = counts
        #print("%s : %d" % (tag, counts))

print(word_count)

# 딕셔너리를 데이터프레임으로 변환
df = pd.DataFrame(list(word_count.items()), columns=['단어', '빈도'])

file_name = filename
file_path = "C:/projects/blogdata/firstsort/"
file_save = file_path + file_name

# CSV 파일로 저장
df.to_csv(file_save, index=False, encoding='utf-8-sig')  # utf-8-sig를 사용하여 한글이 깨지지 않도록 합니다.