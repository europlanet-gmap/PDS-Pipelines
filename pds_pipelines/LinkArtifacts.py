#!/usr/bin/env python

import os
import pvl
import json
import logging
import argparse
from xmljson import badgerfish as bf
from pds_pipelines.config import recipe_base, link_dest
from pds_pipelines.RedisQueue import RedisQueue
from ast import literal_eval
from pds_pipelines.config import pds_log


class Args(object):
    def __init__(self):
        pass

    def parse_args(self):
        parser = argparse.ArgumentParser(description="DI Process")

        parser.add_argument('--log', '-l', dest="log_level",
                            choices=['DEBUG', 'INFO',
                                    'WARNING', 'ERROR', 'CRITICAL'],
                            help="Set the log level.", default='INFO')

        args = parser.parse_args()
        self.log_level = args.log_level


def main():
    RQ = RedisQueue('LinkQueue')
    args = Args()
    args.parse_args()

    logger = logging.getLogger('LINK_Process')
    level = logging.getLevelName(args.log_level)
    logger.setLevel(level)
    logFileHandle = logging.FileHandler(pds_log + 'Link.log')
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s, %(message)s')
    logFileHandle.setFormatter(formatter)
    logger.addHandler(logFileHandle)


    while int(RQ.QueueSize()) > 0:
        # Grab a tuple of values from the redis queue
        item = literal_eval(RQ.QueueGet().decode('utf-8'))
        # Split tuple into two values
        inputfile = item[0]
        archive = item[1]

        json_file_path = recipe_base + archive + '.json'
        try:
            with open(json_file_path, 'r') as f:
                json_dict = json.load(f)
        except ValueError as e:
            logging.warn(e)
            continue
        link_src_path = json_dict['src']

        voldesc = load_pvl(inputfile)
        dataset_id = voldesc['VOLUME']['DATA_SET_ID']
        volume_id = voldesc['VOLUME']['VOLUME_ID']
        # if more than one dataset id exists, link each of them
        if isinstance(dataset_id, (list, tuple, set)):
            [link(link_src_path, link_dest, volume_id, x) for x in dataset_id]
        else:
            # Not container type
            link(link_src_path, link_dest, volume_id, dataset_id)


def format_id(f_id):
    # Remove all quotes, braces, brackets, parentheses, commas, spaces
    formatted_id = ''.join(c for c in f_id if c not in '\'\"{}[](), ')
    formatted_id = formatted_id.replace('/', '_')
    formatted_id = formatted_id.lower()
    return formatted_id


def link(src_path, dest_path, volume_id, dataset_id):
    dataset_id = format_id(dataset_id)
    src = os.path.join(src_path, volume_id)
    dest = os.path.join(dest_path, dataset_id, volume_id)
    link_path = os.path.split(dest)
    if os.path.exists(src):
        os.makedirs(link_path[0], exist_ok=True)
        try:
            os.symlink(src, dest)
        except FileExistsError:
            return
    else:
        src = os.path.join(src_path, volume_id.lower())
        dest = os.path.join(dest_path, dataset_id, volume_id.lower())
        if os.path.exists(src):
            os.makedirs(link_path[0], exist_ok=True)
            try:
                os.symlink(src, dest)
            except FileExistsError:
                return
        else:
            raise(OSError("Unable to locate a source directory for symlink with volume id %s",
                          str(volume_id)))


def load_pvl(pvl_file_path):
    with open(pvl_file_path, 'r') as f:
        f.readline()
        data = f.read()
    voldesc = pvl.loads(data)
    return voldesc


if __name__ == '__main__':
    main()
