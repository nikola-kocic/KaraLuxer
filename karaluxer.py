from argparse import ArgumentParser, Namespace
from pathlib import Path
from math import floor
import re
import shutil

import ass
from ass.line import Dialogue


# Globals
OUTPUT_FOLDER = Path('./out')
NOTE_LINE = ': {start} {duration} {pitch} {sound} \n'
SEP_LINE = '- {0} \n'
BEATS_PER_SECOND = 20
TIMING_REGEX = re.compile(r'(\{\\(?:k|kf|ko|K)[0-9]+\}[a-z|A-Z]*)|({\\(?:k|kf|ko|K)[0-9]+[^}]*\})')


def parse_subtitles(sub_file: Path) -> str:
    """Function to parse an ass file and convert the karaoke timings to the ultrastar format.

    Args:
        sub_file (Path): The path to the ass file.

    Returns:
        str: The notes, mapped to the ultrastar format.
    """

    with open(sub_file, 'r', encoding='utf-8-sig') as f:
        sub_data = ass.parse(f)

    # Output.
    notes_string = ''

    # Filter out comments.
    dialogue_lines = [event for event in sub_data.events if isinstance(event, Dialogue)]

    # Parse lines
    for line in dialogue_lines:
        # Set start of line markers.
        current_beat = floor(line.start.total_seconds() * BEATS_PER_SECOND)

        # Get all syllables and timings for the line.
        syllables = []
        for sound_line, timing_line in re.findall(TIMING_REGEX, line.text):
            if sound_line:
                timing, sound = sound_line.split('}')
            elif timing_line:
                timing = timing_line.split('\\')[1]
                sound = None
            else:
                print('\033[1;33mWarning:\033[0m Something unexpected was found in line - {0}'.format(line.text))
                continue

            timing = re.sub(r'[^0-9]', '', timing)
            syllables.append((int(timing), sound))

        # Write out ultrastar timings.
        for duration_cs, sound in syllables:
            # Karaoke timings in ass files are given in centiseconds.
            duration = floor((duration_cs / 100) * BEATS_PER_SECOND)

            if sound:
                # TODO Some form of basic automatic pitching.
                # Duration is reduced by 1 to give gaps.
                notes_string += NOTE_LINE.format(start=current_beat, duration=duration - 1, sound=sound, pitch=19)

            current_beat += duration

        # Write line separator for ultrastar.
        notes_string += SEP_LINE.format(current_beat)

    return notes_string


def main(args: Namespace) -> None:
    """The main driver for the script.

    Args:
        args (Namespace): The command line arguments.
    """

    base_name = '{0} - {1}'.format(args.artist, args.title)

    song_folder = OUTPUT_FOLDER.joinpath(base_name)
    try:
        song_folder.mkdir(parents=True)
    except FileExistsError:
        print('\033[0;31mError:\033[0m There is already an output for this song!')
        return

    # Load files.
    audio_path = Path(args.audio)
    ass_path = Path(args.ass)
    cover_path = Path(args.cover) if args.cover else None
    background_path = Path(args.background) if args.background else None
    bg_video_path = Path(args.background_video) if args.background_video else None

    # Parse subtitle file.
    notes_section = parse_subtitles(ass_path)

    # Calculate BPM for ultrastar.
    # This script uses a fixed 'beats per second' to produce timings, the BPM for ultrastar is based off the fixed bps.
    # The BPM put into the ultrastar file needs to be around 1/4 of the calculated BPM (I'm not sure why).
    beats_per_minute = (BEATS_PER_SECOND * 60) / 4

    # Produce metadata section of the ultrastar file.
    metadata = '#TITLE:{0}\n#ARTIST:{1}\n'.format(args.title, args.artist)

    if args.language:
        metadata += '#LANGUAGE:{0}\n'.format(args.language)

    if args.creator:
        metadata += '#CREATOR:{0}\n'.format(args.creator)

    # Produce files section of the ultrastar file.
    # Paths are made relative and files will be renamed to match the base name.
    mp3_name = '{0}.mp3'.format(base_name)
    linked_files = '#MP3:{0}\n'.format(mp3_name)
    shutil.copy(audio_path, song_folder.joinpath(mp3_name))

    if cover_path:
        cover_name = '{0} [CO]{1}'.format(base_name, cover_path.suffix)
        linked_files += '#COVER:{0}\n'.format(cover_name)
        shutil.copy(cover_path, song_folder.joinpath(cover_name))

    if background_path:
        background_name = '{0} [BG]{1}'.format(base_name, background_path.suffix)
        linked_files += '#BACKGROUND:{0}\n'.format(background_name)
        shutil.copy(background_path, song_folder.joinpath(background_name))

    if bg_video_path:
        bg_video_name = '{0}{1}'.format(base_name, bg_video_path.suffix)
        linked_files += '#VIDEO:{0}\n'.format(bg_video_name)
        shutil.copy(bg_video_path, song_folder.joinpath(bg_video_name))

    # Produce song data section of the ultrastar file.
    song_data = '#BPM:{0}\n#GAP:0\n'.format(beats_per_minute)

    # Combine ultrastar file components
    ultrastar_file = metadata + linked_files + song_data + notes_section + 'E\n'

    # Write file
    ultrastar_file_path = song_folder.joinpath('{0}.txt'.format(base_name))
    with open(ultrastar_file_path, 'w') as f:
        f.write(ultrastar_file)

    print('\033[0;32mSuccess:\033[0m The ultrastar project has been placed in the output folder!')
    print('\033[1;33mThe song should be checked manually for any mistakes\033[0m')


def init_argument_parser() -> ArgumentParser:
    '''Function to setup the command line argument parser.

    Adds the following arguments:
        * `title`         Specifies the title of the song.
        * `artist`        Specifies the song artist.
        * `audio`         Path to the MP3 file for the song.
        * `ass`           Path to the subtitle file to parse for timings.
        * `-co`           Path to the cover image for the song.
        * `-bg`           Path to the background image for the song.
        * `-bv`           Path to the background video for the song.
        * `-l`            Specifies the language the song is in.
        * `-c`            Specifies the creator of the map.

    Returns:
        ArgumentParser: The command line parser for this program.
    '''

    parser = ArgumentParser()

    parser.add_argument(
        'title',
        help='The title of the song.',
        type=str
    )
    parser.add_argument(
        'artist',
        help='The song artist.',
        type=str
    )
    parser.add_argument(
        'audio',
        help='The path to the MP3 file for the song.',
        type=str
    )
    parser.add_argument(
        'ass',
        help='The path to the subtitle file to parse for timings.',
        type=str
    )
    parser.add_argument(
        '-co',
        '--cover',
        help='The path to the cover image for the song.',
        type=str
    )
    parser.add_argument(
        '-bg',
        '--background',
        help='The path to the background image for the song.',
        type=str
    )
    parser.add_argument(
        '-bv',
        '--background_video',
        help='The path to the background video for the song.',
        type=str
    )
    parser.add_argument(
        '-l',
        '--language',
        help='The language the song is in.',
        type=str
    )
    parser.add_argument(
        '-c',
        '--creator',
        help='The creator of this map.',
        type=str
    )
    return parser


def check_arg_paths(args: Namespace) -> bool:
    """Function to check if all the specified paths are valid.

    Does not check that files are actually valid, only checks the file extension.

    Args:
        args (Namespace): The command line arguments.

    Returns:
        bool: True if all the paths are valid, else False.
    """

    if not Path(args.audio).exists():
        print('\033[0;31mError:\033[0m The specified audio file can not be found!')
        return False

    if not Path(args.ass).exists():
        print('\033[0;31mError:\033[0m The specified subtitle file can not be found!')
        return False

    if args.cover and not Path(args.cover).exists():
        print('\033[0;31mError:\033[0m The specified cover image file can not be found!')
        return False
    elif args.cover:
        if Path(args.cover).suffix in ['jpg', 'jpeg', 'png']:
            print('\033[0;31mError:\033[0m The specified cover image is not an image!')
            return False

    if args.background and not Path(args.background).exists():
        print('\033[0;31mError:\033[0m The specified background image file can not be found!')
        return False
    elif args.cover:
        if Path(args.background).suffix in ['jpg', 'jpeg', 'png']:
            print('\033[0;31mError:\033[0m The specified background image is not an image!')
            return False

    if args.background_video and not Path(args.background_video).exists():
        print('\033[0;31mError:\033[0m The specified background videofile can not be found!')
        return False
    elif args.background_video:
        if Path(args.background_video).suffix != '.mp4':
            print(Path(args.background).suffix)
            print('\033[0;31mError:\033[0m The specified background video is not a mp4!')
            return False

    return True


if __name__ == '__main__':
    parser = init_argument_parser()
    args = parser.parse_args()
    if check_arg_paths(args):
        main(args)