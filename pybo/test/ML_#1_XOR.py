from sklearn import svm, metrics # metrics 추가
import pandas as pd  # pandas 추가
#XOR 결과 데이터

def xor_test():
    xor_data =[
        [0,0,0],
        [0,1,1],
        [1,0,1],
        [1,1,0]
    ]

    # 학습을 위해 데이터와 레이블 분리하기 

    # 1) 일반 방식 ====
    # data =[]
    # label =[]
    # for row in xor_data:
    #     p=row[0]
    #     q=row[1]
    #     r=row[2]
    #     data.append([p,q])
    #     label.append(r)

    # 2) 심플 방식 (pandas 이용)====
    xor_df = pd.DataFrame(xor_data)
    xor_data = xor_df.loc[:,0:1] # 데이터
    xor_label = xor_df.loc[:,2] # 레이블


    # 데이터 학습과 예측 
    # 데이터 학습시키기 -- 일반방식
    # clf = svm.SVC()
    # clf.fit(data, label)


    # 데이터 예측하기 -- 일반방식
    # pre = clf.predict(data)
    # print("예측결과", pre)

    # Simple 방식
    #학습
    clf=svm.SVC() 
    clf.fit(xor_data, xor_label)
    #예측
    pre = clf.predict(xor_data)



    # 결과 확인하기 
    #일반방식
    # ok = 0; total = 0
    # for idx, answer in enumerate(label):
    #     p = pre[idx]
    #     if p == answer : ok += 1
    #     total += 1
    # print("정답률", ok, "/", total, "=", ok/total)

    #정답률 구하기  // metrics 사용 
    ac_score = metrics.accuracy_score(xor_label,pre)
    print ('정답률',ac_score)
