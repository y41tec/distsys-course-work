import argparse
import jwt
import uvicorn

from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse


def parse_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=str)
    parser.add_argument("--port", type=str)
    args = parser.parse_args()

    jwt_public = None
    with open(args.public, "rb") as file:
        jwt_public = file.read()

    return jwt_public, int(args.port)


jwt_public, port = parse_cli()
key_to_username = dict()
key_to_value = dict()
app = FastAPI()


@app.post("/put", response_class=PlainTextResponse)
async def signup(key: str, request: Request):
    cookie = request.cookies.get("jwt")
    if cookie is None:
        raise HTTPException(status_code=401, detail="No cookie found")

    try:
        username = jwt.decode(cookie, jwt_public, ["RS256"])["username"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cookie")

    if key in key_to_username and key_to_username[key] != username:
        raise HTTPException(status_code=403, detail="Invalid key")

    data = await request.json()
    value = data["value"]
    key_to_username[key] = username
    key_to_value[key] = value
    return


@app.get("/get", response_class=JSONResponse)
async def get(key: str, request: Request):
    cookie = request.cookies.get("jwt")
    if cookie is None:
        raise HTTPException(status_code=401, detail="No cookie found")

    try:
        username = jwt.decode(cookie, jwt_public, ["RS256"])["username"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cookie")

    if key not in key_to_username:
        raise HTTPException(status_code=404, detail="No key found")

    if key_to_username[key] != username:
        raise HTTPException(status_code=403, detail="Invalid key")

    response = JSONResponse(content={"value": key_to_value[key]})
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="kv", port=port)
