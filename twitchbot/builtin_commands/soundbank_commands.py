import re,os
from pydub import AudioSegment as pd_audio
from pydub.playback import play as pd_play
from pydub.utils import mediainfo as pd_mediainfo
from twitchbot import (
    Command,
    Message,
    Sound,
    cfg,
    InvalidArgumentsError,
    get_currency_name,
    get_balance_from_msg,
    subtract_balance,
    add_sound,
    get_sound,
    delete_sound,
    clean_sb,
    populate_sb,
    purge_sb
)

PREFIX = cfg.prefix
SB_COOLDOWN = cfg.soundbank_cooldown
SB_PATH = cfg.soundbank_path
SB_DEFPRICE = cfg.soundbank_default_price


@Command('addsound', permission='sound', syntax='<sndid> <filepath> price=(price) pricemult=(pricemult) gain=(gain)', 
    help='adds a sound to the soundboard')
async def cmd_add_sound(msg: Message, *args):
    # sanity checks
    filepath = os.path.join(SB_PATH, args[1])
    if not os.path.exists(filepath):
        raise InvalidArgumentsError(reason='file you are trying to add does not exist', cmd=cmd_add_sound)
    if not args:
        raise InvalidArgumentsError(reason='missing required arguments', cmd=cmd_add_sound)
    sndid=args[0]

    optionals = ' '.join(args[2:])
    optargs = {}
    
    if 'price=' in optionals and 'pricemult=' in optionals:
        raise InvalidArgumentsError(reason='specify price or pricemult, not both!',
            cmd=cmd_add_sound)
    
    if 'price=' in optionals:
        m = re.search(r'price=(\d+)', msg.content)
        if m:
            optargs['price'] = int(m.group(1))
        else:
            raise InvalidArgumentsError(
                reason='invalid price for price=, must be an INT',
                        cmd=cmd_add_sound)
    
    if 'pricemult=' in optionals:
        m = re.search(r'pricemult=(x?)(\d+.\d*)', msg.content)
        if m and float(m.group(2))>=0:
            optargs['pricemult'] = float(m.group(2))
        else:
            raise InvalidArgumentsError(
                reason='invalid argument for pricemult=, must be a non-negative '+
                'FLOAT or xFLOAT, e.g., 0.7 or x1.4', cmd=cmd_add_sound)
    
    if 'gain=' in optionals:
        m = re.search(r'gain=(-?\d+.\d*)', msg.content)
        if m:
            optargs['gain'] = float(m.group(1))
        else: 
            raise InvalidArgumentsError(
                reason='invalid gain for gain=, must be a FLOAT, e.g., -1.4',
                    cmd=cmd_add_sound)
    
    snd = Sound.create(channel=msg.channel_name, sndid=sndid, filepath=filepath, **optargs)
    
    if add_sound(snd):
        resp = f'successfully added sound "{sndid}" to soundboard'
    else:
        resp = 'failed to add sound, already exists'

    await msg.reply(resp)


@Command('updsound', permission='sound', syntax='<sndid> price=(price) pricemult=(pricemult) gain=(gain)', 
    help='updates sound details in the soundboard')
async def cmd_upd_sound(msg: Message, *args):
    # this largely follows the same steps as addsound
    snd = get_sound(msg.channel_name, args[0])
    if snd is None:
        raise InvalidArgumentsError(reason='no sound found with this name', cmd=cmd_upd_sound)
        
    optionals = ' '.join(args[2:])
    
    if 'price=' in optionals and 'pricemult=' in optionals:
        raise InvalidArgumentsError(reason='specify price or pricemult, not both!',
            cmd=cmd_upd_sound)
    
    if 'price=' in optionals:
        m = re.search(r'price=(\d+)', msg.content)
        if m:
            snd.price = int(m.group(1))
        else:
            raise InvalidArgumentsError(
                reason='invalid price for price=, must be an INT',
                        cmd=cmd_upd_sound)
    
    if 'pricemult=' in optionals:
        m = re.search(r'pricemult=(x?)(\d+.\d*)', msg.content)
        if m and float(m.group(2))>=0:
            snd.pricemult = float(m.group(2))
        else:
            raise InvalidArgumentsError(
                reason='invalid argument for pricemult=, must be a non-negative '+
                'FLOAT or xFLOAT, e.g., 0.7 or x1.4', cmd=cmd_upd_sound)
    
    if 'gain=' in optionals:
        m = re.search(r'gain=(-?\d+.\d*)', msg.content)
        if m:
            snd.gain = float(m.group(1))
        else: 
            raise InvalidArgumentsError(
                reason='invalid gain for gain=, must be a FLOAT, e.g., -1.4',
                    cmd=cmd_add_sound)
    
    session.commit()
    await msg.reply(f'successfully updated sound {snd.sndid}')


@Command('sb', syntax='<sndid>', cooldown=SB_COOLDOWN, help='plays sound sndid from soundboard')
async def cmd_get_sound(msg: Message, *args):
    # sanity checks:
    if not args:
        #raise InvalidArgumentsError(reason='missing required argument', cmd=cmd_get_sound)
        await msg.reply(f'You can play sounds from the soundboard with "!sb <sndname>".')
        return

    snd = get_sound(msg.channel_name, args[0])
    if snd is None:
        raise InvalidArgumentsError(reason='no sound found with this name', cmd=cmd_get_sound)
    
    # calculate the sound price
    if snd.price:
        price = snd.price
    elif snd.pricemult:
        price = snd.pricemult*SB_DEFPRICE
    else:
        price = SB_DEFPRICE
    
    # make the author pay the price:
    currency = get_currency_name(msg.channel_name).name
    if get_balance_from_msg(msg).balance < price:
        raise InvalidArgumentsError(f'{msg.author} tried to play {snd.sndid} '
            f'for {price} {currency}, but they do not have enough {currency}!')
    subtract_balance(msg.channel_name, msg.author, price)
    
    # report success
    if cfg.soundbank_verbose:
        await msg.reply(f'{msg.author} played "{snd.sndid}" for {price} {currency}')
    
    # play the sound with PyDub; supports all formats supported by ffmpeg.
    # Tested with mp3, wav, ogg.
    if snd.gain:
        gain = snd.gain
    else:
        gain = 0
    sound = pd_audio.from_file(snd.filepath) + cfg.soundbank_gain + gain
    pd_play(sound)


@Command('delsound', permission='sound', syntax='<sndid>', help='deletes the sound from the soundboard')
async def cmd_del_sound(msg: Message, *args):
    if not args:
        raise InvalidArgumentsError(reason='missing required argument', cmd=cmd_del_sound)

    snd = get_sound(msg.channel_name, args[0])
    if snd is None:
        raise InvalidArgumentsError(reason='no such sound found', cmd=cmd_del_sound)
    
    delete_sound(msg.channel_name, snd.sndid)
    await msg.reply(f'successfully deleted sound "{snd.sndid}"')


@Command('purgesb', permission='sound', help='deletes all sounds from the soundbank')
async def cmd_purge_sb(msg: Message):
    purge_sb(channel=msg.channel_name)
    await msg.reply(f'soundbank purged')


@Command('cleansb', permission='sound', syntax='[q]uiet', help='clears all sounds with missing files from the soundbank')
async def cmd_clean_sb(msg: Message):
    num = clean_sb(channel=msg.channel_name, verbose=not quiet)
    await msg.reply(f'{num} sounds with missing files were deleted')
    

@Command('updatesb', permission='sound', syntax='[r]ecursive [s]trip [f]orce [q]uiet',
    help='auto-imports sounds from the filesystem')
async def cmd_upd_sb(msg: Message, *args):
    optionals = ' '.join(args)
    rec = True if ('r' in optionals) else False 
    strip = True if ('s' in optionals) else False 
    replace = True if ('f' in optionals) else False 
    quiet = True if ('q' in optionals) else False 
    
    num_a,num_r = populate_sb(channel=msg.channel_name, path=SB_PATH, recursive=rec, 
            replace=replace, strip_prefix=strip, verbose=not quiet)
    await msg.reply(f'soundbank updated')
    if replace:
        await msg.reply(f'soundbank updated; {num_a} sounds added, {num_r} sounds replaced')
    else:
        await msg.reply(f'soundbank updated; {num_a} sounds added')


@Command('gensblist', permission='sound', help='output list of sounds in soundbank (with prices) to file')
async def cmd_gen_sb_list(msg: Message):
    channel=msg.channel_name
    with open(f"{SB_PATH}/sb_list_{channel}.txt", 'w') as f:
        f.write(f'# Soundbank [sub]commands list for channel {channel}\n\n')
        f.write('# AUTOMATICALLY GENERATED FILE\n')
        currency = get_currency_name(snd.channel).name
        for snd in session.query(Sound).filter(Sound.channel == channel).all():
            if snd.price:
                price=snd.price
            elif snd.pricemult:
                price = snd.pricemult*SB_DEFPRICE
            else:
                price=SB_DEFPRICE
            f.write(f'{PREFIX}sb {snd.sndid}\t\t{price} {currency}\n')
    await msg.reply(f'sound list generated')
