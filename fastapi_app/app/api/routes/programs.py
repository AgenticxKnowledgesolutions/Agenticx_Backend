from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.program import ProgramCreate, ProgramUpdate, ProgramResponse
from app.services import program_service
from app.deps import require_admin
from app.models.user import User
from app.models.program import Program

router = APIRouter(prefix="/programs", tags=["programs"])


@router.get("/", response_model=List[ProgramResponse])
async def list_programs(db: AsyncSession = Depends(get_db)):
    return await program_service.list_programs(db)


@router.get("/trash", response_model=List[ProgramResponse])
async def list_trash_programs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await program_service.list_trash_programs(db)


@router.get("/{slug}", response_model=ProgramResponse)
async def get_program(slug: str, db: AsyncSession = Depends(get_db)):
    program = await program_service.get_program_by_slug(db, slug)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.post("/", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    data: ProgramCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        return await program_service.create_program(db, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: str,
    data: ProgramUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    program = await program_service.get_program_orm(db, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return await program_service.update_program(db, program, data)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    program = await program_service.get_program_orm(db, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    await program_service.delete_program(db, program, current_user.email)


@router.post("/{program_id}/restore", response_model=ProgramResponse)
async def restore_program(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return await program_service.restore_program(db, program)


@router.delete("/{program_id}/hard-delete", status_code=status.HTTP_200_OK)
async def hard_delete_program(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    await program_service.hard_delete_program(db, program)
    return {"detail": "Program permanently deleted"}
