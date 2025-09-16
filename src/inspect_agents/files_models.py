"""File operation models and parameters.

This module contains Pydantic models for file operations, extracted from
tools_files.py to enable faster imports and focused unit testing.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, RootModel


# Result types
class FileReadResult(BaseModel):
    """Typed result for read operations."""

    lines: list[str]
    summary: str


class FileWriteResult(BaseModel):
    """Typed result for write operations."""

    path: str
    summary: str


class FileEditResult(BaseModel):
    """Typed result for edit operations.

    When `dry_run=True`, no mutation is performed; `replaced` reflects the
    number of replacements that would have been applied given current file
    contents and the `replace_all` flag.
    """

    path: str
    replaced: int
    summary: str


class FileDeleteResult(BaseModel):
    """Typed result for delete operations."""

    path: str
    summary: str


class FileTrashResult(BaseModel):
    """Typed result for trash operations (audited delete)."""

    src: str
    dst: str
    summary: str


class FileListResult(BaseModel):
    """Typed result for ls operations."""

    files: list[str]


class FileMoveResult(BaseModel):
    """Typed result for move operations."""

    src: str
    dst: str
    summary: str


class FileStatResult(BaseModel):
    """Typed result for stat operations."""

    path: str
    exists: bool
    is_dir: bool
    size: int | None


# Parameter schemas for each command
class BaseFileParams(BaseModel):
    """Base parameters for all file operations."""

    instance: str | None = Field(None, description="Optional Files instance for isolation")

    # Pydantic v2 style config
    model_config = ConfigDict(extra="forbid")


class LsParams(BaseFileParams):
    """Parameters for ls command."""

    command: Literal["ls"] = "ls"


class ReadParams(BaseFileParams):
    """Parameters for read command."""

    command: Literal["read"] = "read"
    file_path: str = Field(description="Path to read")
    offset: int = Field(0, description="Line offset (0-based)")
    limit: int = Field(2000, description="Max lines to return")


class WriteParams(BaseFileParams):
    """Parameters for write command."""

    command: Literal["write"] = "write"
    file_path: str = Field(description="Path to write")
    content: str = Field(description="Content to write")


class EditParams(BaseFileParams):
    """Parameters for edit command."""

    command: Literal["edit"] = "edit"
    file_path: str = Field(description="Path to edit")
    old_string: str = Field(description="String to replace")
    new_string: str = Field(description="Replacement string")
    replace_all: bool = Field(False, description="Replace all occurrences if true")
    dry_run: bool = Field(False, description="When true, compute result without persisting changes")
    expected_count: int | None = Field(
        None,
        description=(
            "Optional expected number of replacements to perform. When set, the edit "
            "will validate that exactly this many replacements would occur and raise "
            "an error on mismatch."
        ),
    )


class MkdirParams(BaseFileParams):
    """Parameters for mkdir command."""

    command: Literal["mkdir"] = "mkdir"
    dir_path: str = Field(description="Directory path to create")


class MoveParams(BaseFileParams):
    """Parameters for move command."""

    command: Literal["move"] = "move"
    src_path: str = Field(description="Source path")
    dst_path: str = Field(description="Destination path")


class StatParams(BaseFileParams):
    """Parameters for stat command."""

    command: Literal["stat"] = "stat"
    path: str = Field(description="Path to stat")
    dry_run: bool = Field(
        False,
        description=("When true, compute counts and validate but do not modify the file."),
    )


class DeleteParams(BaseFileParams):
    """Parameters for delete command."""

    command: Literal["delete"] = "delete"
    file_path: str = Field(description="Path to delete")


class TrashParams(BaseFileParams):
    """Parameters for trash command (audited delete)."""

    command: Literal["trash"] = "trash"
    file_path: str = Field(description="Path to move into trash")


class FilesParams(RootModel):
    """Discriminated union of all file operation parameters."""

    root: Annotated[
        LsParams
        | ReadParams
        | WriteParams
        | EditParams
        | DeleteParams
        | TrashParams
        | MkdirParams
        | MoveParams
        | StatParams,
        Discriminator("command"),
    ]
