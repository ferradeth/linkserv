from dataclasses import dataclass
from flask import Flask, request, jsonify, make_response, redirect
from flask_sqlalchemy import SQLAlchemy
import hashlib
import random
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
database = SQLAlchemy(app)
with app.app_context():
    database.create_all()

jwt = JWTManager(app)
app.config['JWT_SECRET_KEY'] = 'jwt-secret-string'


@dataclass
class Users(database.Model):
    # __tablename__ = 'users'
    id: int
    login: str
    password: str

    id = database.Column(database.Integer, primary_key=True)
    login = database.Column(database.String(64))
    password = database.Column(database.String(64))


@dataclass
class Links(database.Model):
    # __tablename__ = 'links'
    id: int
    fullName: str
    shortName: str
    access: int
    userId: int
    countLink: int

    id = database.Column(database.Integer, primary_key=True)
    userId = database.Column(database.Integer)
    fullName = database.Column(database.String(256))
    shortName = database.Column(database.String(12))
    access = database.Column(database.Integer)
    countLink = database.Column(database.Integer)


#регистрация
@app.route("/reg", methods=["POST"])
def reg():
    username = request.json['login']
    password = request.json['password']
    if username.strip() == "":
        return make_response('Проверьте логин')
    elif password.strip() == "":
        return make_response('Проверьте пароль')
    elif username.strip() == "" and password.strip() == "":
        return make_response('Отсутствуют данные для регистрации')
    else:
        if Users.query.filter_by(login=username).first() is None:
            database.session.add(Users(login=username, password=password))
            database.session.commit()
            print('Пользователь зарегистрировался')
            return make_response('Успешная регистрация')
    return make_response('Такой пользователь уже существует')


#авторизация
@app.route("/auth", methods=["POST"])
def login():
    username = request.json['login']
    password = request.json['password']

    if Users.query.filter_by(login=username).first() is not None:
        if database.session.execute(database.select(Users.password).filter_by(login=username)).first()[0] == password:
            return make_response(f'Успешный вход в систему, токен: {create_access_token(identity=username)}')
        else:
            print(username)
            print(password)
            print(database.session.execute(database.select(Users.password).filter_by(login=username)).first())
            return make_response('Неправильные данные для входа')
    else:
        return make_response('Отсутсвует пользователь')


#добавление ссылки в базу
@app.route("/add-link", methods=["POST"])
@jwt_required()
def add_link():
    long_link = request.json['link']
    nickname = request.json['nickname']
    user_token = get_jwt_identity()
    lvl_access = request.json['access']
    user_id = database.session.execute(database.select(Users.id).filter_by(login=user_token)).first()[0]

    if request.json['nickname'] is None:
        if Users.query.filter_by(user_id=user_id, fullName=long_link).all() is None:
            short_link = hashlib.md5(long_link.encode()).hexdigest()[:random.randint(8, 12)]
            database.session.add(Links(fullName=long_link, shortName=short_link, access=lvl_access, userId=user_id))
            database.session.commit()
            return make_response(f'Ссылка сокращена и доступна для перехода по сокращению {short_link}')
        else:
            return make_response("Такая ссылка уже существует в базе")

    else:
        if Users.query.filter_by(shortName=nickname).all() is None:
            if Users.query.filter_by(user_id=user_id, fullName=long_link).all() is None:
                database.session.add(Links(fullName=long_link, shortName=nickname, access=lvl_access, userId=user_id))
                database.session.commit()
                return make_response('Ссылка сокращена и доступна для перехода по вашему сокращению')
            else:
                return make_response("Такая ссылка уже существует в базе")
        else:
            return make_response("Такое название для ссылки недоступно, выберите другое")


#сокращение ссылки без авторизации
@app.route("/get_short", methods=["POST"])
def hash_link():
    long_link = request.json['link']
    short_link = hashlib.md5(long_link.encode()).hexdigest()[:random.randint(8, 12)]
    return make_response(f'Ваша сокращённая ссылка: {short_link}')


#редактирование ссылки
@app.route("/edit_link", methods=["POST"])
@jwt_required()
def edit_link():
    long_link = request.json['link']
    nickname = request.json['nick']
    access = request.json['access']
    user_id = database.session.execute(database.select(Users.id).filter_by(login=get_jwt_identity())).first()[0]

    if nickname == "":
        short_link = hashlib.md5(long_link.encode()).hexdigest()[:random.randint(8, 12)]
        Links.query.filter_by(userId=user_id, fullName=long_link).update({'shortName': short_link, 'access': access})
        database.session.commit()
        return make_response(f"Ваша ссылка {long_link} успешно обновлена")
    else:
        Links.query.filter_by(userId=user_id, fullName=long_link).update({'shortName': nickname, 'access': access})
        database.session.commit()
        return make_response(f"Ваша ссылка {long_link} успешно обновлена")


#получение ссылок пользователя
@app.route("/my_links", methods=["POST"])
@jwt_required()
def get_links():
    user_id = database.session.execute(database.select(Users.id).filter_by(login=get_jwt_identity())).first()[0]
    links = Links.query.filter_by(userId=user_id).all()
    return jsonify(links)


#переход по ссылке
@app.route("/<short>", methods=["POST"])
@jwt_required(optional=True)
def go_to_link(short):
    search_link = database.session.execute(
        database.select(Links.fullName, Links.access, Links.countLink).filter_by(shortName=short)).first()
    print(search_link)
    if search_link[1] == 1:
        if search_link[2] is None:
            count = 1
        else:
            count = search_link[2] + 1
        Links.query.filter_by(fullName=search_link[0]).update({"countLink": count})
        database.session.commit()
        return redirect(search_link[0])
    elif search_link[1] == 2:
        if get_jwt_identity() is not None:
            if search_link[2] is None:
                count = 1
            else:
                count = search_link[2] + 1
            Links.query.filter_by(fullName=search_link[0]).update({"countLink": count})
            database.session.commit()
            return redirect(search_link[0])
        else:
            return make_response("Эта ссылка с ограниченным доступом, необходимо авторизоваться")


#удаление ссылки
@app.route("/delete", methods=["POST"])
@jwt_required()
def delete_link():
    long_link = request.json['link']
    user_id = database.session.execute(database.select(Users.id).filter_by(login=get_jwt_identity())).first()[0]

    Links.query.filter_by(userId=user_id, fullName=long_link).delete()
    database.session.commit()
    return make_response(f"Ваша ссылка {long_link} успешно удалена")


if __name__ == "__main__":
    app.run()
