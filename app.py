import os, datetime, pytz, json

# flask
from flask import Flask, request, abort

# firebase
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Use a service account
cred = credentials.Certificate(os.path.join(os.getcwd(), 'secret', 'firebase.json'))
firebase_admin.initialize_app(cred)

db = firestore.client()

# linebot(https://github.com/line/line-bot-sdk-python)
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError, LineBotApiError
)

from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)

app = Flask(__name__)

if app.env == 'development':
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'), override=True)

dstr = lambda s: '>' + str(s) + '<'
errorstr = lambda s: '[error] ' + str(s)


class Question:

    def __init__(self, *, id=None, text, solved=False, userid, groupid, created_time=None, solved_time=None):
        self.id = id
        self.text = text
        self.solved = solved
        self.userid = userid
        self.groupid = groupid
        self.created_time = created_time if created_time is not None else datetime.datetime.now().astimezone(
            tz=pytz.utc)
        self.solved_time = solved_time

        # self.id = int(id) if id is not None else int(getGroup(self.groupid).get().to_dict()['id_next'])

    def set_solved(self):
        self.solved = True
        self.solved_time = datetime.datetime.now().astimezone(tz=pytz.utc)
        self.update()

    @staticmethod
    def from_dict(dic, *, groupid, set_id=None):
        q = Question(
            text=dic['text'],
            solved=dic['solved'],
            userid=dic['userid'],
            groupid=groupid,
            created_time=dic['created_time'],
            solved_time=dic['solved_time']
        )
        if set_id:
            q.id = int(set_id)
        return q

    def to_dict(self):
        return {
            'text': self.text,
            'solved': self.solved,
            'userid': self.userid,
            'created_time': self.created_time,
            'solved_time': self.solved_time
        }

    @classmethod
    def load_all(cls, groupid, unsolved=False):
        qs = getGroup(groupid).collection('questions')
        stream = qs.stream() if not unsolved else qs.where('solved', '==', False).stream()

        return [cls.from_dict(q.to_dict(), groupid=groupid, set_id=q.id) for q in stream]

    @classmethod
    def load(cls, *, id, groupid):
        q = getGroup(groupid, addGroupIfNotFound=False).collection('questions').document(str(id)).get()
        if not q.exists:
            raise FetchError()
        return cls.from_dict(q.to_dict(), groupid=groupid, set_id=q.id)

    def update(self):
        q = getGroup(self.groupid).collection('questions').document(str(self.id))
        if q.get().exists:
            q.update(self.to_dict())
        else:
            raise FetchError('question not found; hence it cannot be updated')

    def save(self):
        gp = getGroup(self.groupid)
        if self.id is None:
            '''save as new question if id is not given'''
            newid = gp.get().to_dict()['id_next']
            self.id = newid
            gp.update({'id_next': newid + 1})
        gp.collection('questions').document(str(self.id)).set(self.to_dict())

    @staticmethod
    def deleteById(groupid, id):
        q = getGroup(groupid).collection('questions').document(str(id))
        if q.get().exists:
            q.delete()
            return True
        return False

    def delete(self):
        Question.deleteById(groupid=self.groupid,id=self.id)

    def __str__(self):
        username=None
        try:
            username = line_bot_api.get_group_member_profile(group_id=self.groupid,user_id=self.userid).display_name
        except LineBotApiError as e:
            print(e.status_code)
            print(e.request_id)
            print(e.error.message)
            print(e.error.details)

            try:
                username=line_bot_api.get_profile(user_id=self.userid).display_name
            except LineBotApiError as e:
                print(e.status_code)
                print(e.request_id)
                print(e.error.message)
                print(e.error.details)

        text=f'{self.id}. "{self.text}"'
        return text+f'--from[{username}]' if username is not None else text


def getGroup(groupid, addGroupIfNotFound=True):
    gp = db.collection('questions').document(groupid)
    if not gp.get().exists:
        if addGroupIfNotFound:
            addGroup(groupid)
        else:
            raise FetchError()
    return gp


def addGroup(groupid):
    gp = db.collection('questions').document(groupid)
    if gp.get().exists:
        return
    gp.set({
        'id_next': 0
    })
    print(f'group "{groupid}" is created')


class FetchError(Exception):
    """raised when failed to get data from firebase"""
    pass


# *********** 以下為 X-LINE-SIGNATURE 驗證程序 ***********
# certification tokens
# documentation: https://developers.line.me/console/
line_secret = json.load(open(os.path.join(os.getcwd(), 'secret', 'line.json')))
CHANNEL_ACCESS_TOKEN = line_secret['channel_access_token']
CHANNEL_SECRET = line_secret['channel_secret']
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print('[X-Line-Signature 驗證失敗]')
        abort(400)

    return 'OK'


# *********** 以上為 X-LINE-SIGNATURE 驗證程序 ***********

@app.route('/', methods=('GET',))
def index():
    return 'OK', 200


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print('*' * 40)
    print('[使用者傳入文字訊息]')
    print(str(event))
    print(event.message.text)
    print(event.source.type)

    user_msg = event.message.text.strip()
    reply = None

    if (user_msg.startswith('?') or user_msg.startswith('？')) and len(user_msg) > 1 and event.source.type=='group':
        command = user_msg[1:].lstrip()
        q = Question(
            text=command,
            userid=event.source.user_id,
            groupid=event.source.group_id
        )
        q.save()
        reply = TextSendMessage(text=dstr(f"question [{q.id}] is saved"))
    elif user_msg.startswith('/') and len(user_msg) > 1 and event.source.type=='group':
        command = user_msg[1:].split()
        if groupid := event.source.group_id:
            if command[0].lower() == 'all':
                qs = Question.load_all(groupid)
                if not len(qs):
                    reply = TextSendMessage(text=dstr("(empty)"))
                else:
                    reply = TextSendMessage(text=dstr("\n" + "\n".join([str(q) for q in qs]) + "\n"))
            elif command[0].lower() == 'uns':
                qs = Question.load_all(groupid, unsolved=True)
                if not len(qs):
                    reply = TextSendMessage(text=dstr("(empty)"))
                else:
                    reply = TextSendMessage(text=dstr("\n" + "\n".join([str(q) for q in qs]) + "\n"))
            elif command[0].lower() == 'del':
                if len(command) >= 2:
                    if command[1].lower() == 'all':
                        qs = Question.load_all(groupid=groupid)
                        for q in qs:
                            q.delete()
                        reply = TextSendMessage(text=dstr(f"all questions are deleted"))
                    else:
                        try:
                            num = int(command[1])
                        except ValueError:
                            reply = TextSendMessage(text=errorstr("the first argument of '/del' must be an integer or 0"))
                        else:
                            if Question.deleteById(groupid, num):
                                reply = TextSendMessage(text=dstr(f"question [{num}] is deleted"))
                else:
                    reply = TextSendMessage(text=errorstr("'/del' missing required argument 'id'"))
            elif command[0].lower() == 's':
                if len(command)>=2:
                    if command[1].lower()=='all':
                        qs = Question.load_all(groupid=groupid,unsolved=True)
                        for q in qs:
                            q.set_solved()
                        reply = TextSendMessage(text=dstr(f"all questions are solved"))
                    else:
                        try:
                            num = int(command[1])
                        except ValueError:
                            reply = TextSendMessage(text=errorstr("the first argument of '/s' must be an integer or 0"))
                        else:
                            try:
                                q = Question.load(id=num, groupid=groupid)
                            except FetchError:
                                reply = TextSendMessage(text=errorstr(f"question [{num}] is not found"))
                            else:
                                q.set_solved()
                                reply = TextSendMessage(text=dstr(f"question [{num}] is solved"))
                else:
                    reply = TextSendMessage(text=errorstr("'/s' missing required argument 'id'"))

    # 回傳訊息
    if reply:
        line_bot_api.reply_message(
            event.reply_token,
            reply
        )


if __name__ == "__main__":
    print('[server starts]')
    port = int(os.environ.get('PORT', 8080))
    print('[Flask is now listening port:{}]'.format(port))
    app.run(port=port)
