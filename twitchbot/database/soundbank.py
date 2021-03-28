import os
from pydub.utils import mediainfo as pd_mediainfo
from typing import Optional
from .models import Sound
from .session import session

__all__ = ('add_sound', 'get_sound', 'delete_sound', 'purge_sb', 'clean_sb', 'populate_sb')


def add_sound(snd: Sound) -> bool:
    """add a sound object to the soundbank, return a bool indicating if it was successful"""
    assert isinstance(snd, Sound), 'sound must be of type Sound'

    if sound_exist(snd.channel, snd.sndid, snd.filepath):
        return False

    session.add(snd)
    session.commit()
    return True


def get_sound(channel: str, sndid: str) -> Optional[Sound]:
    """return a Sound object from the soundback given sndid"""
    assert isinstance(sndid, str), 'sound sndid must be of type str'
    return session.query(Sound).filter(Sound.channel == channel, Sound.sndid == sndid).one_or_none()


def delete_sound(channel: str, sndid: str) -> None:
    """delete a sound by sndid"""
    assert isinstance(sndid, str), 'sound sndid must be of type str'
    session.query(Sound).filter(Sound.channel == channel, Sound.sndid == sndid).delete()
    session.commit()


def purge_sb(channel: str) -> None:
    """delete all entries from soundbank"""
    session.query(Sound).filter(Sound.channel == channel).delete()
    session.commit()


def clean_sb(channel: str, verbose: bool = True) -> int:
    """remove unused files and add new files to soundbank"""
    num=0
    for snd in session.query(Sound).filter(Sound.channel == channel).all():
        if not os.path.exists(snd.filepath):
            session.delete(snd)
            num+=1
            if verbose:
                print(f'sound "{snd.sndid}" has been deleted because the associated file was not found ({snd.filepath})')
            
    session.commit()
    return num


def _filename_strip(filename: str, strip_prefix: bool = False) -> str:
    """convert a file name to a sndid for automated processing"""
    # (just the file name expected, without path)
    # first identify and strip the prefix, if any and if needed
    if strip_prefix:
        prefixpos = filename.find("_")
    else: 
        prefixpos = -1
    
    # then strip the file extension (defined via the last dot)
    # also drop anything after the first space because no spaces allowed in sndid
    suffixpos1 = filename.rfind(".")
    suffixpos2 = filename.find(" ")
    # not really sure how to simplify these ifs
    if suffixpos1 > -1 and suffixpos2 > -1:
        suffixpos = min(suffixpos1, suffixpos2)
    elif suffixpos1 > -1:
        suffixpos = suffixpos1
    elif suffixpos2 > -1:
        suffixpos = suffixpos2
    else:
        suffixpos = None
    
    return filename[prefixpos+1:suffixpos]


def populate_sb(channel: str, path: str = '.', recursive: bool = False, replace: bool = False, 
            strip_prefix: bool = False, verbose: bool = True):
    """auto-fill the soundbank (for given channel) from files in the specified folder"""
    if not os.path.exists(path):
        return False
    
    # Generate the relevant list of files
    scanfiles = []
    if recursive:
        for root, subdirs, files in os.walk(path):
            for file in files:
                scanfiles.append([root, file])
    else:
        for file in os.listdir(path):
            if os.path.isdir(file):
                continue
            scanfiles.append([path, file])
    
    # Attempt to import files into database
    num_a=0
    num_r=0
    for froot,fname in scanfiles:
        # Generate full file path
        fpath = os.path.join(froot, fname)
        
        # Check if pydub can recognize these files 
        if not pd_mediainfo(fpath):
            continue
        
        sndid = _filename_strip(fname, strip_prefix)
        snd = Sound.create(channel=channel, sndid=sndid, filepath=fpath)
        
        # Try to add the file
        sndex = get_sound(channel=channel, sndid=sndid)
        if not sndex:
            # no conflicts, add sound
            session.add(snd)
            resp = f'successfully added sound "{sndid}" to soundboard from {fpath}'
            num_a+=1
        elif replace:
            # sndid exists and is overwritten
            session.query(Sound).filter(Sound.channel == channel, Sound.sndid == sndid).delete()
            session.add(snd)
            resp = f'replaced sound "{sndid}" from {fpath}'
            num_r+=1
        elif sndex.filepath==snd.filepath:
            # sndid exists and is same file
            resp = f'sound "{sndid}" already exists from {fpath}'
        else:
            # sndid exists but points to a different file
            resp = f'failed to add sound "{sndid}" from {fpath}: sndid already taken by {sndex.filepath}'
        
        if verbose:
            print(resp)
    
    session.commit()
    if verbose:
        print('changes to db successfully committed')
    return num_a,num_r
