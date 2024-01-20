from pymongo import MongoClient
import jwt
import datetime
import hashlib
from flask import Flask, render_template, jsonify, request, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["UPLOAD_FOLDER"] = "./static/profile_pics"

SECRET_KEY = "SPARTA"

MONGODB_CONNECTION_STRING = "mongodb+srv://localhost:maulana20065@cluster0.ewovbxv.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGODB_CONNECTION_STRING)
db = client.dbsparta_plus_week4


@app.route("/")
def home():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        user_info = db.user.find_one({"username": payload["id"]})
        return render_template("index.html", user_info=user_info)
    except jwt.ExpiredSignatureError:
        return redirect(url_for("login", msg="Your token has expired"))
    except jwt.exceptions.DecodeError:
        return redirect(url_for("login", msg="There was problem logging you in"))


@app.route("/login")
def login():
    msg = request.args.get("msg")
    return render_template("login.html", msg=msg)


@app.route("/user/<username>")
def user(username):
    # an endpoint for retrieving a user's profile information
    # and all of their posts
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        # if this is my own profile, True
        # if this is somebody else's profile, False
        status = username == payload["id"]

        user_info = db.user.find_one({"username": username}, {"_id": False})
        return render_template("user.html", user_info=user_info, status=status)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/sign_in", methods=["POST"])
def sign_in():
    # Sign in
    username_receive = request.form["username_give"]
    password_receive = request.form["password_give"]
    pw_hash = hashlib.sha256(password_receive.encode("utf-8")).hexdigest()
    print(username_receive, pw_hash)
    result = db.user.find_one(
        {
            "username": username_receive,
            "password": pw_hash,
        }
    )
    if result:
        payload = {
            "id": username_receive,
            # the token will be valid for 24 hours
            "exp": datetime.utcnow() + timedelta(seconds=60 * 60 * 24),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify(
            {
                "result": "success",
                "token": token,
            }
        )
    # Let's also handle the case where the id and
    # password combination cannot be found
    else:
        return jsonify(
            {
                "result": "fail",
                "msg": "We could not find a user with that id/password combination",
            }
        )


@app.route("/sign_up/save", methods=["POST"])
def sign_up():
    username_receive = request.form["username_give"]
    password_receive = request.form["password_give"]
    password_hash = hashlib.sha256(password_receive.encode("utf-8")).hexdigest()
    doc = {
        "username": username_receive,  # id
        "password": password_hash,  # password
        "profile_name": username_receive,  # user's name is set to their id by default
        "profile_pic": "",  # profile image file name
        "profile_pic_real": "profile_pics/profile_placeholder.png",  # a default profile image
        "profile_info": "",  # a profile description
    }
    db.user.insert_one(doc)
    return jsonify({"result": "success"})


@app.route("/sign_up/check_dup", methods=["POST"])
def check_dup():
    # ID we should check whether or not the id is already taken
    username_receive = request.form["username_give"]
    exists = bool(db.user.find_one({"username": username_receive}))
    return jsonify({"result": "success", "exists": exists})


@app.route("/update_profile", methods=["POST"])
def save_img():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        username = payload["id"]
        name_receive = request.form["name_give"]
        about_receive = request.form["about_give"]
        new_doc = {"profile_name": name_receive, "profile_info": about_receive}
        if "file_give" in request.files:
            file = request.files["file_give"]
            filename = secure_filename(file.filename)
            extension = filename.split(".")[-1]
            file_path = f"profile_pics/{username}.{extension}"
            file.save("./static/" + file_path)
            new_doc["profile_pic"] = filename
            new_doc["profile_pic_real"] = file_path
        db.user.update_one({"username": payload["id"]}, {"$set": new_doc})
        return jsonify({"result": "success", "msg": "Profile updated!"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/posting", methods=["POST"])
def posting():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        # We should create a new post here
        user_info = db.user.find_one({"username": payload["id"]})
        comment_receive = request.form["comment_give"]
        date_receive = request.form["date_give"]
        doc = {
            "username": user_info["username"],
            "profile_name": user_info["profile_name"],
            "profile_pic_real": user_info["profile_pic_real"],
            "comment": comment_receive,
            "date": date_receive,
        }
        db.posts.insert_one(doc)
        return jsonify({"result": "success", "msg": "Posting successful!"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/get_posts", methods=["GET"])
def get_posts():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])

        username_receive = request.args.get("username_give")
        if username_receive == "":
            posts = list(db.posts.find({}).sort("date", -1).limit(20))
        else:
            posts = list(
                db.posts.find({"username": username_receive}).sort("date", -1).limit(20)
            )

        for post in posts:
            post["_id"] = str(post["_id"])
            post["count_heart"] = db.likes.count_documents(
                {"post_id": post["_id"], "type": "heart"}
            )
            post["heart_by_me"] = bool(
                db.likes.find_one(
                    {"post_id": post["_id"], "type": "heart", "username": payload["id"]}
                )
            )
        return jsonify(
            {
                "result": "success",
                "msg": "Successful fetched all posts",
                "posts": posts,
            }
        )
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/update_like", methods=["POST"])
def update_like():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        # We should change the like count for the post here
        user_info = db.user.find_one({"username": payload["id"]})
        post_id_receive = request.form["post_id_give"]
        type_receive = request.form["type_give"]
        action_receive = request.form["action_give"]
        doc = {
            "post_id": post_id_receive,
            "username": user_info["username"],
            "type": type_receive,
        }
        if action_receive == "like":
            db.likes.insert_one(doc)
        else:
            db.likes.delete_one(doc)
        count = db.likes.count_documents(
            {"post_id": post_id_receive, "type": type_receive}
        )
        return jsonify({"result": "success", "msg": "updated", "count": count})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/secret")
def secret():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        return render_template("secret.html")
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


@app.route("/register")
def register():
    return render_template("register.html")


#################################
## Login related API endpoints ##
#################################


# [Signup API]
# Kita akan menerima data id, password, dan nickname dari
# user dan menyimpannya di MongoDb
# Sebelum menyimpan passwordnya, kita pertama-tama akan mengenkripsinya
# menggunakan fungsi hashing SHA256
@app.route("/api/register", methods=["POST"])
def api_register():
    id_receive = request.form["id_give"]
    pw_receive = request.form["pw_give"]
    nickname_receive = request.form["nickname_give"]

    pw_hash = hashlib.sha256(pw_receive.encode("utf-8")).hexdigest()

    db.user.insert_one({"id": id_receive, "pw": pw_hash, "nick": nickname_receive})

    return jsonify({"result": "success"})


# [Login Endpoint API]
# Kita menerima id dan password dari user,
# dan kemudian mengeluarkan sebuah token JWT untuk mereka gunakan
@app.route("/api/login", methods=["POST"])
def api_login():
    id_receive = request.form["id_give"]
    pw_receive = request.form["pw_give"]

    # Kita akan mengenkripsi passwordnya disini dengan
    # cara yang sama seperti user pertama kali mendaftar untuk layanan web

    pw_hash = hashlib.sha256(pw_receive.encode("utf-8")).hexdigest()

    # kita menggunakan id user dan password yang terenkripsi untuk
    # mencari user tersebut di database
    result = db.user.find_one({"id": id_receive, "pw": pw_hash})

    # Jika kita bisa menemukan user tersebut, kita membuat
    # Tokej JWT baru untuk mereka
    if result is not None:
        # Untuk menghasilkan token JWT, kita perlu
        # suatu "payload" dan "kunci rahasia"

        # "kunci rahasia" diperlukan untuk mendekripsi
        # token dan melihat payload

        # payload dibawah membawa id user dan tanggal expired token,
        # artinya anda jika anda dekripsi tokennya, anda
        # bisa tau id user

        # jika kita mengatur "exp" tanggal expired, lalu suatu errror
        # muncul ketika kita mencoba dekripsi tokennya menggunakan
        # kunci rahasia ketika token telah expired. Ini merupakan hal bagus!
        payload = {
            "id": id_receive,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=5),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        # mengembalikan token ke client
        return jsonify({"result": "success", "token": token})
    # Jika kita tidak bisa menemukan user di database,
    # kita bisa menangani kasus tersebut disini
    else:
        return jsonify(
            {"result": "fail", "msg": "Either your email or your password is incorrect"}
        )


# [Endpoint API verifikasi informasi user]
# Ini merupakan endpoint API yang hanya bisa
# menerima request dari user terotentikasi
# Anda hanya perlu memasukkan token yang valid
# pada request anda untuk mendapatkan akses ke
# Endpoint API ini. Sistem ini wajar karena
# beberapa informasi sebaiknya private untuk setiap user
# (contoh. shopping cart atau data akun user)
@app.route("/api/nick", methods=["GET"])
def api_valid():
    token_receive = request.cookies.get("mytoken")

    # apakah anda sudah melihat pernyataan try/catch sebelumnya?
    try:
        # kita akan coba decode tokennya dengan kunci rahasia
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        # jika tidak ada masalah, kita seharusnya melihat
        # payload terdekripsi muncul di terminal kita!
        print(payload)

        # payload terdekripsinya seharusnya berisi id user
        # kita bisa menggunakan id ini untuk mencari data user
        # dari database dan mengembalikannya ke user
        userinfo = db.user.find_one({"id": payload["id"]}, {"_id": 0})
        return jsonify({"result": "success", "nickname": userinfo["nick"]})
    except jwt.ExpiredSignatureError:
        # jika anda mencoba untuk mendekripsi token yang sudah expired
        # anda akan mendapatkan error khusus, kita menangani error nya disini
        return jsonify({"result": "fail", "msg": "Your token has expired"})
    except jwt.exceptions.DecodeError:
        # jika ada permasalahan lain ketika proses decoding,
        # kita akan tangani di sini
        return jsonify(
            {"result": "fail", "msg": "There was an error while logging you in"}
        )


if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)
