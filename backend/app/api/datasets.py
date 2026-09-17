"""
DataGuard AI — Dataset Management & Ingestion API Router

Handles file upload, validation, parsing, version sequence tracking,
and PostgreSQL dataset persistence.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dataset import (
    UploadResponse,
    DatasetListItem,
    DatasetDetailResponse,
    DatasetVersionSummary,
)
from app.services.ingestion import (
    IngestionError,
    validate_file,
    save_uploaded_file,
    parse_csv,
    parse_excel,
    generate_metadata,
)
from app.services.dataset_service import (
    normalize_dataset_name,
    get_or_create_dataset,
    create_dataset_version,
    list_datasets,
    get_dataset_detail,
    get_dataset_version,
    delete_dataset,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


# ---------------------------------------------------------------------------
# Upload & Ingest Dataset
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV or Excel spreadsheet, inspect schema & quality statistics,
    and persist into the dataset versioning system.
    """
    # 1. Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read the uploaded file.",
        )

    file_size = len(file_content)
    original_filename = file.filename or "unknown"
    content_type = file.content_type

    logger.info(
        f"Upload received: '{original_filename}' ({file_size} bytes, type={content_type})"
    )

    # 2. Validate file
    try:
        ext = validate_file(original_filename, content_type, file_size)
    except IngestionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 3. Save file safely
    try:
        stored_path = save_uploaded_file(file_content, original_filename, ext)
        stored_filename = stored_path.name
    except IngestionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 4. Parse content with pandas
    try:
        if ext == "csv":
            df, encoding, delimiter = parse_csv(file_content)
            sheet_name = None
        elif ext == "xlsx":
            df, sheet_name = parse_excel(file_content)
            encoding = None
            delimiter = None
        else:
            raise IngestionError(f"Unsupported extension: .{ext}")
    except IngestionError as e:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 5. Extract column metadata and sample preview
    try:
        norm_name = normalize_dataset_name(dataset_name, original_filename)
        metadata = generate_metadata(
            df=df,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_type=ext,
            file_size=file_size,
            encoding=encoding,
            delimiter=delimiter,
            sheet_name=sheet_name,
        )
        metadata.dataset_name = norm_name
    except Exception as e:
        logger.error(f"Metadata generation failed: {e}")
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate dataset metadata.",
        )

    # 6. Persist to PostgreSQL within transaction
    try:
        dataset_entity = get_or_create_dataset(
            db=db,
            name=norm_name,
            description=description,
        )
        version_entity = create_dataset_version(
            db=db,
            dataset=dataset_entity,
            metadata=metadata,
        )
        db.commit()

        # Update response with persistent IDs
        metadata.dataset_id = dataset_entity.id
        metadata.version_id = version_entity.id
        metadata.version_number = version_entity.version_number

        logger.info(
            f"Upload persisted: '{norm_name}' V{version_entity.version_number} "
            f"({metadata.row_count} rows x {metadata.column_count} cols)"
        )
    except Exception as e:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        logger.error(f"Database persistence failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist dataset to database.",
        )

    return metadata


# ---------------------------------------------------------------------------
# List All Datasets
# ---------------------------------------------------------------------------
@router.get("", response_model=list[DatasetListItem])
def get_all_datasets(db: Session = Depends(get_db)):
    """
    List all datasets in the repository with version summary counts.
    """
    try:
        return list_datasets(db)
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve datasets from database.",
        )


# ---------------------------------------------------------------------------
# Get Dataset Details & Version History
# ---------------------------------------------------------------------------
@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(dataset_id: UUID, db: Session = Depends(get_db)):
    """
    Get full metadata and version history for a specific logical dataset.
    """
    try:
        detail = get_dataset_detail(db, dataset_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset with ID '{dataset_id}' not found.",
            )
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dataset details.",
        )


# ---------------------------------------------------------------------------
# Get Specific Dataset Version
# ---------------------------------------------------------------------------
@router.get(
    "/{dataset_id}/versions/{version_id}",
    response_model=DatasetVersionSummary,
)
def get_version(
    dataset_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get details of a specific version under a dataset.
    """
    try:
        version = get_dataset_version(db, dataset_id, version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{version_id}' not found under dataset '{dataset_id}'.",
            )
        return version
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching version {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch version details.",
        )


# ---------------------------------------------------------------------------
# Delete Dataset
# ---------------------------------------------------------------------------
@router.delete("/{dataset_id}")
def remove_dataset(dataset_id: UUID, db: Session = Depends(get_db)):
    """
    Delete a dataset and all associated versions and physical upload files.
    """
    try:
        success = delete_dataset(db, dataset_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset with ID '{dataset_id}' not found.",
            )
        return {
            "message": "Dataset and all associated versions deleted successfully.",
            "dataset_id": str(dataset_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dataset.",
        )
