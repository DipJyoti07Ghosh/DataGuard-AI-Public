"""
DataGuard AI — Dataset & Versioning Persistence Service

Manages logical dataset identification, version sequence generation,
and transactional persistence in PostgreSQL.
"""

import logging
import re
from pathlib import Path
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.schemas.dataset import (
    DatasetListItem,
    DatasetDetailResponse,
    DatasetVersionSummary,
    UploadResponse,
)

logger = logging.getLogger(__name__)


def normalize_dataset_name(raw_name: str | None, original_filename: str) -> str:
    """
    Determine and normalize the logical dataset name.

    If an explicit name is supplied by user/API, cleans it up.
    Otherwise, deterministically uses the file stem (e.g. 'clean_sample.csv' -> 'clean_sample').
    """
    if raw_name and raw_name.strip():
        name = raw_name.strip()
    else:
        name = Path(original_filename).stem

    # Replace invalid filesystem/URL characters with spaces/underscores, preserve letters & numbers
    name = re.sub(r"[\t\r\n]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100]


def get_or_create_dataset(
    db: Session, name: str, description: str | None = None
) -> Dataset:
    """
    Find an existing logical dataset by name, or create a new one.
    """
    stmt = select(Dataset).where(Dataset.name == name)
    dataset = db.scalar(stmt)

    if not dataset:
        dataset = Dataset(name=name, description=description)
        db.add(dataset)
        db.flush()  # assign dataset.id without committing outer transaction
        logger.info(f"Created new Dataset entity: '{name}' (id={dataset.id})")
    else:
        logger.info(f"Reusing existing Dataset entity: '{name}' (id={dataset.id})")

    return dataset


def create_dataset_version(
    db: Session,
    dataset: Dataset,
    metadata: UploadResponse,
) -> DatasetVersion:
    """
    Create and persist a new sequential snapshot version for a logical dataset.

    Calculates the next version number inside the transaction to ensure strict sequencing.
    """
    # Determine next version number (MAX + 1 or 1)
    max_v_stmt = select(func.max(DatasetVersion.version_number)).where(
        DatasetVersion.dataset_id == dataset.id
    )
    max_v = db.scalar(max_v_stmt)
    next_version = (max_v or 0) + 1

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=next_version,
        original_filename=metadata.original_filename,
        stored_filename=metadata.stored_filename,
        file_type=metadata.file_type,
        file_size_bytes=metadata.file_size_bytes,
        row_count=metadata.row_count,
        column_count=metadata.column_count,
        column_names=metadata.column_names,
        column_dtypes=metadata.column_dtypes,
        encoding=metadata.encoding,
        delimiter=metadata.delimiter,
        sheet_name=metadata.sheet_name,
        uploaded_at=metadata.uploaded_at,
    )

    db.add(version)
    db.flush()  # assign version.id

    logger.info(
        f"Persisted Dataset '{dataset.name}' Version V{next_version} (id={version.id})"
    )
    return version


def list_datasets(db: Session) -> list[DatasetListItem]:
    """
    Retrieve all logical datasets with aggregated version count and latest metadata.
    """
    datasets = db.scalars(
        select(Dataset).order_by(Dataset.updated_at.desc())
    ).all()

    result = []
    for ds in datasets:
        versions = ds.versions
        if versions:
            # versions are sorted by version_number DESC via relationship
            latest = versions[0]
            item = DatasetListItem(
                id=ds.id,
                name=ds.name,
                description=ds.description,
                version_count=len(versions),
                latest_version_number=latest.version_number,
                latest_upload_time=latest.uploaded_at,
                latest_row_count=latest.row_count,
                latest_column_count=latest.column_count,
                created_at=ds.created_at,
                updated_at=ds.updated_at,
            )
        else:
            item = DatasetListItem(
                id=ds.id,
                name=ds.name,
                description=ds.description,
                version_count=0,
                latest_version_number=0,
                latest_upload_time=ds.created_at,
                latest_row_count=0,
                latest_column_count=0,
                created_at=ds.created_at,
                updated_at=ds.updated_at,
            )
        result.append(item)

    return result


def get_dataset_detail(db: Session, dataset_id: UUID) -> DatasetDetailResponse | None:
    """
    Get full dataset information including all versions.
    """
    dataset = db.scalar(select(Dataset).where(Dataset.id == dataset_id))
    if not dataset:
        return None

    versions_summary = [
        DatasetVersionSummary(
            id=v.id,
            dataset_id=v.dataset_id,
            version_number=v.version_number,
            original_filename=v.original_filename,
            stored_filename=v.stored_filename,
            file_type=v.file_type,
            file_size_bytes=v.file_size_bytes,
            row_count=v.row_count,
            column_count=v.column_count,
            column_names=v.column_names,
            column_dtypes=v.column_dtypes,
            encoding=v.encoding,
            delimiter=v.delimiter,
            sheet_name=v.sheet_name,
            uploaded_at=v.uploaded_at,
        )
        for v in dataset.versions
    ]

    return DatasetDetailResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        versions=versions_summary,
    )


def get_dataset_version(
    db: Session, dataset_id: UUID, version_id: UUID
) -> DatasetVersionSummary | None:
    """
    Get details of a specific dataset version.
    """
    stmt = select(DatasetVersion).where(
        DatasetVersion.id == version_id, DatasetVersion.dataset_id == dataset_id
    )
    v = db.scalar(stmt)
    if not v:
        return None

    return DatasetVersionSummary.model_validate(v)


def delete_dataset(db: Session, dataset_id: UUID) -> bool:
    """
    Delete a dataset and its versions from database, and clean up referenced files on disk.
    """
    dataset = db.scalar(select(Dataset).where(Dataset.id == dataset_id))
    if not dataset:
        return False

    upload_dir = settings.upload_path
    # Collect files to remove after successful DB delete
    files_to_remove = []
    for v in dataset.versions:
        safe_file = upload_dir / v.stored_filename
        try:
            # Confirm file is inside upload_dir to prevent arbitrary file deletion
            if safe_file.resolve().is_relative_to(upload_dir.resolve()):
                files_to_remove.append(safe_file)
        except Exception:
            pass

    db.delete(dataset)
    db.commit()

    # Clean up physical files
    for file_path in files_to_remove:
        try:
            file_path.unlink(missing_ok=True)
            logger.info(f"Deleted physical file: {file_path.name}")
        except Exception as e:
            logger.warning(f"Could not remove file {file_path}: {e}")

    logger.info(f"Deleted dataset id={dataset_id}")
    return True
