import argparse
import jwt
import uvicorn

from hashlib import md5
from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse


def parse_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", type=str)
    parser.add_argument("--public", type=str)
    parser.add_argument("--port", type=str)
    args = parser.parse_args()

    jwt_private, jwt_public = None, None
    with open(args.private, "rb") as file:
        jwt_private = file.read()
    with open(args.public, "rb") as file:
        jwt_public = file.read()

    return jwt_private, jwt_public, int(args.port)


jwt_private, jwt_public, port = parse_cli()
username_to_hash = dict()
app = FastAPI()


@app.post("/signup", response_class=JSONResponse)
async def signup(request: Request):
    data = await request.json()
    username, password = data["username"], data["password"]
    if username in username_to_hash:
        raise HTTPException(status_code=403, detail="User exists")

    user_hash = md5(f"{username}:{password}".encode("utf-8")).hexdigest()
    username_to_hash[username] = user_hash

    response = JSONResponse(content={})
    response.set_cookie(
        key="jwt",
        value=jwt.encode(
            {"username": username, "password": password}, jwt_private, "RS256"
        ),
    )
    return response


@app.post("/login", response_class=JSONResponse)
async def login(request: Request):
    data = await request.json()
    username, password = data["username"], data["password"]
    user_hash = md5(f"{username}:{password}".encode("utf-8")).hexdigest()
    if username not in username_to_hash:
        raise HTTPException(status_code=403, detail="User doesnt exist")
    if username_to_hash[username] != user_hash:
        raise HTTPException(status_code=403, detail="Invalid password")

    response = JSONResponse(content={})
    response.set_cookie(
        key="jwt",
        value=jwt.encode(
            {"username": username, "password": password}, jwt_private, "RS256"
        ),
    )
    return response


@app.get("/whoami", response_class=PlainTextResponse)
async def whoami(request: Request):
    cookie = request.cookies.get("jwt")
    if cookie is None:
        raise HTTPException(status_code=401, detail="No cookie found")

    try:
        username = jwt.decode(cookie, jwt_public, ["RS256"])["username"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cookie")

    if username not in username_to_hash:
        raise HTTPException(status_code=400, detail="Invalid cookie")

    response = f"Hello, {username}"
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="auth", port=port)
