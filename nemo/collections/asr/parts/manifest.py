# Copyright (c) 2019 NVIDIA Corporation
import json
from os.path import expanduser
from typing import Any, Callable, Dict, Iterator, List, Optional, Union


class ManifestBase:
    def __init__(self, *args, **kwargs):
        raise ValueError(
            "This class is deprecated, look at https://github.com/NVIDIA/NeMo/pull/284 for correct behaviour."
        )


class ManifestEN:
    def __init__(self, *args, **kwargs):
        raise ValueError(
            "This class is deprecated, look at https://github.com/NVIDIA/NeMo/pull/284 for correct behaviour."
        )


def item_iter(
    manifests_files: Union[str, List[str]], parse_func: Callable[[str, Optional[str]], Dict[str, Any]] = None
) -> Iterator[Dict[str, Any]]:
    """Iterate through json lines of provided manifests.

    NeMo ASR pipelines often assume certain manifest files structure. In
    particular, each manifest file should consist of line-per-sample files with
    each line being correct json dict. Each such json dict should have a field
    for audio file string, a field for duration float and a field for text
    string. Offset also could be additional field and is set to None by
    default.

    Args:
        manifests_files: Either single string file or list of such -
            manifests to yield items from.

        parse_func: A callable function which accepts as input a single line
            of a manifest and optionally the manifest file itself,
            and parses it, returning a dictionary mapping from str -> Any.

    Yields:
        Parsed key to value item dicts.

    Raises:
        ValueError: If met invalid json line structure.
    """

    if isinstance(manifests_files, str):
        manifests_files = [manifests_files]

    if parse_func is None:
        parse_func = __parse_item

    for manifest_file in manifests_files:
        with open(expanduser(manifest_file), 'r') as f:
            for line in f:
                item = parse_func(line, manifest_file)

                yield item


def __parse_item(line: str, manifest_file: str) -> Dict[str, Any]:
    item = json.loads(line)

    # Audio file
    if 'audio_filename' in item:
        item['audio_file'] = item.pop('audio_filename')
    elif 'audio_filepath' in item:
        item['audio_file'] = item.pop('audio_filepath')
    else:
        raise ValueError(
            f"Manifest file {manifest_file} has invalid json line " f"structure: {line} without proper audio file key."
        )
    item['audio_file'] = expanduser(item['audio_file'])

    # Duration.
    if 'duration' not in item:
        raise ValueError(
            f"Manifest file {manifest_file} has invalid json line " f"structure: {line} without proper duration key."
        )

    # Text.
    if 'text' in item:
        pass
    elif 'text_filepath' in item:
        with open(item.pop('text_filepath'), 'r') as f:
            item['text'] = f.read().replace('\n', '')
    else:
        raise ValueError(
            f"Manifest file {manifest_file} has invalid json line " f"structure: {line} without proper text key."
        )

    item = dict(
        audio_file=item['audio_file'], duration=item['duration'], text=item['text'], offset=item.get('offset', None),
    )

    return item
