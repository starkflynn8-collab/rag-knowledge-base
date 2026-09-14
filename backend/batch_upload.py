import shutil
import uuid
from pathlib import Path, PureWindowsPath

import config_data as config


def ingest_uploaded_directory(service, files, include_noise_html, dry_run, operator):
    if not files:
        raise ValueError('请选择包含文件的目录')
    paths = []
    seen = set()
    for upload in files:
        name = (upload.filename or '').replace('\\', '/')
        parts = name.split('/')
        if (PureWindowsPath(name).drive or any(part in {'', '.', '..'} for part in parts)
                or any(any(char in part for char in ':<>"|?*\x00') or part.endswith((' ', '.'))
                       or PureWindowsPath(part).is_reserved() for part in parts)):
            raise ValueError('目录中存在非法文件路径')
        if name.casefold() in seen:
            raise ValueError('目录中存在重复文件路径')
        seen.add(name.casefold())
        paths.append(Path(*parts))

    batch_id = uuid.uuid4().hex
    root = Path(config.PROJECT_ROOT) / 'uploads' / 'batches' / batch_id
    root.mkdir(parents=True)
    importing = False
    try:
        total = 0
        for upload, relative in zip(files, paths):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('wb') as output:
                while chunk := upload.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > 512 * 1024 * 1024:
                        raise ValueError('单次目录上传不能超过 512 MB，请分批导入')
                    output.write(chunk)
        # Keep originals after import, including CSS/images used by HTML previews.
        importing = not dry_run
        result = service.batch_ingest(str(root), include_noise_html, dry_run, operator,
                                      source_prefix=f'_uploads/{batch_id}')
        result['path'] = paths[0].parts[0]
        result['uploaded_files'] = len(files)
        return result
    finally:
        if not importing:
            shutil.rmtree(root)
