import threading
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
import pytesseract
import requests as rq
from bs4 import BeautifulSoup

VALIDATE_CODE_SAVE_PATH = "./code.jpg"
THREAD_NUM = 5
# 线程全局变量，False代表没有任何一个线程请求成功了。
SUCCESS_STATUS = False
# 线程全局变量，False代表没有任何一个线程登录成功了。
LOGINED_STATUS = False
# 用于全局共享登录Cookie，只要有一个线程登录成功了，其他的线程公用一个Cookie，不进行反复登录。
SHARE_SESSION_COOKIE = None

MORNING = True
AFTERNOON = False
ANY_TIME = True
NOT_ANY_TIME = False
ROLE_STUDENT = False
ROLE_PERSON = True


class Predictor:
    def __init__(self, save_path, username, passwd, role=True, times=False, any_times=False, point_time=""):
        self.save_path = save_path
        self.username = username
        self.passwd = passwd
        # 由于只存在英文字母，对于识别出的近似的数字转换成对应的英文字母
        self.error_dict = {"9": "g", "0": "o", "1": "l", "$": "s", "|": "l", "2": "z"
            , "/": "l", "€": "c", "@": "a"}
        # 选择你要报考的类型,True 社会人员 False 在校大学生
        self.role = role
        # 选择你要报考的时间段，True为上午，False 为下午
        self.times = times
        # 任意时间都可 Ture为都可以 false要自定义
        self.any_times = any_times
        # 指定日期
        self.point_time = point_time
        # 全局session
        self.sess = rq.session()
        # 是否已经登录
        self.login = False
        # 存储获取的考试信息
        self.datas = None
        self.image = None

    # 二值化处理，去除无用的背景噪音
    def preprocess(self):
        image_body = self.sess.get("http://cltt.51hzks.cn/validateCheckCode")
        # 保存图像
        roiImg = Image.open(BytesIO(image_body.content))
        # 腐蚀和膨胀卷积核
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        gray = cv2.cvtColor(np.array(roiImg), cv2.COLOR_BGR2GRAY)
        ret, binary = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        # 去除零散的噪点
        eroded = cv2.erode(binary, kernel)
        dilated = cv2.dilate(eroded, kernel)
        # 保存图像到本地 修改：VALIDATE_CODE_SAVE_PATH
        if self.save_path != "" or None:
            cv2.imwrite(self.save_path, dilated)
        return dilated

    # 解析考试信息
    def parse_exam_info(self):
        if self.check_success():
            return []
        try:
            body = self.sess.get("http://cltt.51hzks.cn/queryExamInfo")
            soup = BeautifulSoup(body.text, 'html.parser')
            l = soup.select("table > tr")
            datas = []
            if "登录时间" in body.text:
                print("登录成功！")
            for i in range(2, len(l)):
                tds = l[i].select("td")
                d = {"考试场次": tds[0].get_text(), "报名截止时间": tds[1].get_text().strip(), "考试时间": tds[2].get_text().strip(),
                     "报名对象": tds[3].get_text().strip(), "考试地址": tds[4].get_text().strip(),
                     "考试人数": tds[5].get_text().strip(), "预报名人数": tds[6].get_text().strip(),
                     "需缴费用(元)": tds[7].get_text().strip(), "操作": tds[8], "是否符合条件": True}
                opreation_select_data = tds[8].select("a")
                if len(opreation_select_data) == 0:
                    d["是否符合条件"] = False
                # 当报名对象是社会人员，而role是false（学生时）
                if d["报名对象"] == "社会人员" and not self.role:
                    d["是否符合条件"] = False
                # 当报名对象是学生，而role是社会人员
                if d["报名对象"] != "社会人员" and self.role:
                    d["是否符合条件"] = False
                if len(opreation_select_data) > 0:
                    # <a class="czbtn" href="#" onclick="AdvanceRegister('170','65.00','2')" title="">预报名</a>
                    #  '操作': ['169', '65.00', '2'],
                    d["操作"] = d["操作"].select("a")[0]['onclick'].strip()[16:-1].replace("'", "").split(",")
                datas.append(d)
            return datas
        except Exception as e:
            print("解析考试信息出错", e)
            return None

    # 报名请求函数
    # http://cltt.51hzks.cn/advanceRegister
    # ?examUserRegisterInfoDomain.examId=170&examUserRegisterInfoDomain.requestPayCost=65.00
    def apply_for(self, data):
        print("选择的考次为：", data)
        operation = data['操作']
        if self.check_success():
            return True
        try:
            apply_body = self.sess.get("http://cltt.51hzks.cn/advanceRegister", params={
                "examUserRegisterInfoDomain.examId": operation[0],
                "examUserRegisterInfoDomain.requestPayCost": [1]
            })
        except Exception as e:
            print("提交报名失败,重新提交:", e)
            return self.apply_for(data)  # 重复提交，直到成功
        if "预报名成功" in apply_body.text:
            # 代表预报名成功
            return True
        return False

    # 获取登录状态
    def get_login(self):
        return self.login

    def parse_filter(self):
        if self.check_success():
            return True
        # 筛选所有满足条件
        for l in self.datas:
            if l["是否符合条件"]:
                if self.any_times:
                    return self.apply_for(l)
                if self.times:
                    # 上午
                    if "上午" in l['考试场次']:
                        if self.point_time != "" and self.point_time in l['考试场次']:
                            return self.apply_for(l)
                        elif self.point_time == "":
                            return self.apply_for(l)
                        else:
                            continue

                else:
                    # 下午
                    if "下午" in l['考试场次']:
                        if self.point_time != "" and self.point_time in l['考试场次']:
                            return self.apply_for(l)
                        elif self.point_time == "":
                            return self.apply_for(l)
                        else:
                            continue
        print("没有找到任何考场信息！")
        return False

    def check_success(self):
        global SUCCESS_STATUS
        global LOGINED_STATUS
        global SHARE_SESSION_COOKIE

        # 直接获取其他线程已经登录的cookie，跳过重复登录
        if LOGINED_STATUS:
            print("检测到其他线程已经登录完成，共享Cookie")
            self.sess.cookies.set("JSESSIONID", SHARE_SESSION_COOKIE)

        if SUCCESS_STATUS:
            return SUCCESS_STATUS
        return False

    # 解析验证码
    def parse_code(self):
        try:
            # 获取验证码图片，进行预处理，去除背景噪音
            self.image = self.preprocess()
            ocr_result = ""
            ret_result = {"status": False, "result": ""}
            result = pytesseract.image_to_string(self.image)
            # 合并多个ocr结果
            for r in result:
                ocr_result = ocr_result + r.strip().lower().replace(" ", "")
            print(ocr_result)
            # 对部分识别错误字进行修正，因为验证码只能由英文组成，不包括数字和其他的字符
            for d in ocr_result:
                if self.error_dict.get(d, None) is not None:
                    ocr_result = ocr_result.replace(d, self.error_dict.get(d, None))
            # 如果长度不满足4，则一定是存在错误
            if len(ocr_result) != 4:
                print("验证码长度不满足，重试:", result)
                return self.parse_code()
            ret_result['status'] = True
            ret_result['result'] = ocr_result
            return ret_result
        except Exception as e:
            print("解析验证码出现错误,重新识别", e)
            return self.parse_code()

    # 登录函数
    def auto_login(self):
        global SHARE_SESSION_COOKIE
        global LOGINED_STATUS
        if self.check_success():
            self.login = True
            return self.sess
        # 验证码解析
        ret_result = self.parse_code()
        code = ret_result['result']
        print("识别到的验证码为：", code)
        login_body = self.sess.post("http://cltt.51hzks.cn/studentLogin.action", data={
            "studentInfoDomain.identification": self.username,
            "studentInfoDomain.password": self.passwd,
            "studentInfoDomain.verificationCode": code
        })
        # 操作员：XXX&nbsp;登录时间：2021-08-09 13:19:21
        # 出现上述内容说明登录成功
        if "登录时间" in login_body.text:
            print("登录成功！")
            # success
            self.login = True
            LOGINED_STATUS = True
            # 保存JSESSIONID,共享
            SHARE_SESSION_COOKIE = self.sess.cookies.get("JSESSIONID")
            return self.sess
        else:
            print("尝试登录失败，可能原因：验证码错误、网络错误、账号错误、密码错误。")
        return None

    def do(self):
        # 循环登录，直到登录成功
        print("登录操作：", "开始登录")
        while not self.get_login():
            try:
                while self.auto_login() is None:
                    print("登录操作：", "登录失败，重试中。")
            except Exception as e:
                print("登录操作：", "登录异常，重试中。", e)
                continue
        print("登录操作：", "登录结束")
        print("考场操作：", "获取考场信息中")
        while self.datas is None:
            self.datas = self.parse_exam_info()
            print("考场操作：", "获取考场信息失败，重试中")
        print("考场操作：", "获取考场信息结束，开始报名")
        status = self.parse_filter()
        print("考场操作：", "执行完成")
        # return True
        return status


def circle():
    global SUCCESS_STATUS
    predictor = Predictor(save_path=VALIDATE_CODE_SAVE_PATH,  # 验证码保存地址
                          username="330381199701094110",  # 用户名
                          passwd="h378759617",  # 密码
                          any_times=NOT_ANY_TIME,  # 是否任意时间都可，默认选择第一个 ANY_TIME 任何时间，屏蔽其他选项 NOT_ANY_TIME
                          role=ROLE_STUDENT,  # ROLE_PERSON 社会人士 ROLE_STUDENT 学生
                          point_time="",  # 指派时间 如20210901,默认为空
                          times=MORNING)  # MORNING 早上，AFTERNOON 下午，如果any_times为ANY_TIME则该选项无效
    SUCCESS_STATUS = predictor.do()


# 单线程执行
circle()

# 多线程执行
# for i in range(THREAD_NUM):
#     t = threading.Thread(target=circle)
#     t.start()
#     t.join()
