# 杭州普通话报名

> 每次抢普通话根本抢不到，于是开发此项目用于快速抢普通话名额
> 
> 本项目仅供学习使用

## 依赖库

PIL

cv2

numpy

easyocr

requests

BeautifulSoup4

## 功能

* 自动识别验证码
* 多线程执行
* 自定义指定时间

## 使用

### 单线程执行
```python
# 单线程执行
circle()
```

### 多线程执行
```python
# 多线程执行
for i in range(THREAD_NUM):
    t = threading.Thread(target=circle)
    t.start()
    t.join()
```

## 参数

```python
THREAD_NUM = 10 # 线程数
```

```python
def circle():
    global SUCCESS_STATUS
    predictor = Predictor(save_path=VALIDATE_CODE_SAVE_PATH,  # 验证码保存地址
                          username="XXXXXXXXXXXX",  # 用户名
                          passwd="XXXXXXXX",  # 密码
                          any_times=NOT_ANY_TIME,  # 是否任意时间都可，默认选择第一个 ANY_TIME 任何时间，屏蔽其他选项 NOT_ANY_TIME
                          role=ROLE_STUDENT,  # ROLE_PERSON 社会人士 ROLE_STUDENT 学生
                          point_time="",  # 指派时间 如20210901,默认为空
                          times=MORNING)  # MORNING 早上，AFTERNOON 下午，如果any_times为ANY_TIME则该选项无效
    SUCCESS_STATUS = predictor.do()
```


```
save_path: 验证码保存地址，为空即不保存
username: 用户名
passwd: 密码
any_times：(NOT_ANY_TIME)(不选择任意时间) (ANY_TIME)(任意时间)
role：(ROLE_STUDENT)(学生考场) (ROLE_PERSON)(社会人士考场)
point_time:指派时间 如20210901,默认为空
times:(MORNING)(早上)(AFTERNOON)(下午)
```

