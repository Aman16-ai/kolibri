import io
import logging
import os
import tempfile
import uuid

import unicodecsv as csv

from .constants import drivetypes

logger = logging.getLogger(__name__)

_DRIVE_TYPES = [drivetypes.UNKNOWN, "#noroot", drivetypes.USB_DEVICE, drivetypes.INTERNAL_DRIVE, drivetypes.NETWORK_DRIVE, drivetypes.OPTICAL_DRIVE, "#ram"]

def get_drive_list():

    drives = []

    drive_list = _parse_wmic_csv_output(_wmic_output())

    for drive in drive_list:

        # look up the drive type name
        drivetype = _DRIVE_TYPES[int(drive.get("DriveType") or "0")]

        # skip drives that have invalid types
        if drivetype.startswith("#"):
            logger.debug("Skipping drive '{}' with invalid type: {}".format(drive.get("DeviceID"), drivetype))
            continue

        # construct a path (including "\") from DeviceID, plus fallbacks in case it's not defined for some reason
        path = "{}\\".format(drive.get("DeviceID") or drive.get("Caption") or drive.get("Name"))

        # skip if there's an indication that this is an empty CD-ROM
        if not drive.get("Size"):
            continue

        # skip if we don't have read access to the drive
        if not os.access(path, os.R_OK):
            continue

        # combine the metadata, using backup fields for missing pieces, and return
        drives.append({
            "path": path,
            "name": drive.get("VolumeName") or drive.get("Description"),
            "filesystem": drive.get("FileSystem").lower(),
            "freespace": int(drive.get("FreeSpace") or 0),
            "totalspace": int(drive.get("Size") or 0),
            "drivetype": drivetype,
            "guid": drive.get("VolumeSerialNumber"),
        })

    return drives

def _output_path():
    return os.path.join(
        tempfile.gettempdir(),
        "kolibri_disks-{}.txt".format(uuid.uuid4())
    )

def _wmic_output():
    """
    Returns the output from running the built-in `wmic` command.

    Redirects the output of `wmic` to a temporary file and then reads it back in.
    This would be cleaner if done using subprocess, but attempting to capture
    `stdout` internally led to freezing under Windows XP. (This may have been
    happening because the script is not being run as a main process.)
    """

    OUTPUT_PATH = _output_path()

    cmd = "wmic logicaldisk list full /format:csv > {}".format(OUTPUT_PATH)
    returnCode = os.system(cmd)
    if returnCode:
        raise Exception("Could not run command '{}'".format(cmd))

    with io.open(OUTPUT_PATH, 'r', encoding='utf-16') as f:
        output = f.read()

    os.remove(OUTPUT_PATH)

    return output

def _parse_wmic_csv_output(text):
    """
    Parse the output of Windows "wmic logicaldisk list full /format:csv" command.
    """

    # parse out the comma-separated values of each non-empty row
    rows = [row for row in csv.reader(text.split("\n")) if row]

    # use the first row as the header row
    header = rows.pop(0)

    # turn each row into a dict, mapping the header text of each column to the row's value for that column
    return [dict(zip(header, row)) for row in rows]
