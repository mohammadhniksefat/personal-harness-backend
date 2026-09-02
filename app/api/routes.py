import asyncio, json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from app.db.database import SessionLocal
from app.db.models import Session, Message, Memory, Approval
from app.services.agent import execute, manager

router = APIRouter()


def dbdep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatIn(BaseModel):
    message: str


class MemoryIn(BaseModel):
    key: str
    value: str


@router.post("/sessions")
def create(db: DBSession = Depends(dbdep)):
    s = Session()
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title, "status": s.status}


@router.get("/sessions")
def sessions(db: DBSession = Depends(dbdep)):
    return [
        {"id": s.id, "title": s.title, "status": s.status}
        for s in db.query(Session).order_by(Session.id.desc()).all()
    ]


@router.get("/sessions/{sid}/messages")
def messages(sid: int, db: DBSession = Depends(dbdep)):
    return [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in db.query(Message)
        .filter(Message.session_id == sid)
        .order_by(Message.id)
        .all()
    ]


@router.get("/memory")
def memories(db: DBSession = Depends(dbdep)):
    return [
        {"id": m.id, "key": m.key, "value": m.value} for m in db.query(Memory).all()
    ]


@router.post("/memory")
def memory(x: MemoryIn, db: DBSession = Depends(dbdep)):
    m = db.query(Memory).filter(Memory.key == x.key).first() or Memory(
        key=x.key, value=x.value
    )
    m.value = x.value
    db.add(m)
    db.commit()
    return {"ok": True}


@router.post("/approvals/{aid}")
def approval(aid: int, action: str, db: DBSession = Depends(dbdep)):
    a = db.get(Approval, aid)
    if not a:
        raise HTTPException(404)
    if action not in ("approve", "reject"):
        raise HTTPException(400)
    a.status = "approved" if action == "approve" else "rejected"
    db.commit()
    return {"status": a.status}


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str):
    manager.stop(run_id)
    return {"ok": True}


@router.post("/sessions/{sid}/chat")
async def chat(sid: int, x: ChatIn, db: DBSession = Depends(dbdep)):
    if not db.get(Session, sid):
        raise HTTPException(404)
    q = asyncio.Queue()

    async def emit(e):
        await q.put(e)

    task = asyncio.create_task(execute(db, sid, x.message, emit))

    async def gen():
        while True:
            if task.done() and q.empty():
                break
            try:
                e = await asyncio.wait_for(q.get(), 0.5)
                yield f"data: {json.dumps(e,default=str)}\n\n"
            except asyncio.TimeoutError:
                continue
        await task
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
