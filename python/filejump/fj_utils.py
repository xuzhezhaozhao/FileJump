#!/usr/bin/env python
#
# Copyright (C) 2011, 2012  Google Inc.
#
# This file is part of YouCompleteMe.
#
# YouCompleteMe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# YouCompleteMe is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with YouCompleteMe.  If not, see <http://www.gnu.org/licenses/>.

import tempfile
import os
import sys
import signal
import functools
import socket
import stat
import json
import subprocess
import collections

WIN_PYTHON27_PATH = 'C:\python27\python.exe'
WIN_PYTHON26_PATH = 'C:\python26\python.exe'
# Creation flag to disable creating a console window on Windows. See
# https://msdn.microsoft.com/en-us/library/windows/desktop/ms684863.aspx
CREATE_NO_WINDOW = 0x08000000
# Executable extensions used on Windows
WIN_EXECUTABLE_EXTS = [ '.exe', '.bat', '.cmd' ]


def SanitizeQuery( query ):
  return query.strip()


# Given an object, returns a str object that's utf-8 encoded.
def ToUtf8IfNeeded( value ):
  if isinstance( value, unicode ):
    return value.encode( 'utf8' )
  if isinstance( value, str ):
    return value
  return str( value )


def ToUnicodeIfNeeded( value ):
  if isinstance( value, unicode ):
    return value
  if isinstance( value, str ):
    # All incoming text should be utf8
    return unicode( value, 'utf8' )
  return unicode( value )


# Recurses through the object if it's a dict/iterable and converts all the
# unicode objects to utf-8 strings.
def RecursiveEncodeUnicodeToUtf8( value ):
  if isinstance( value, unicode ):
    return value.encode( 'utf8' )
  if isinstance( value, str ):
    return value
  elif isinstance( value, collections.Mapping ):
    return dict( map( RecursiveEncodeUnicodeToUtf8, value.iteritems() ) )
  elif isinstance( value, collections.Iterable ):
    return type( value )( map( RecursiveEncodeUnicodeToUtf8, value ) )
  else:
    return value


def ToUtf8Json( data ):
  return json.dumps( RecursiveEncodeUnicodeToUtf8( data ),
                     ensure_ascii = False,
                     # This is the encoding of INPUT str data
                     encoding = 'utf-8' )


def PathToTempDir():
  tempdir = os.path.join( tempfile.gettempdir(), 'ycm_temp' )
  try:
    os.makedirs( tempdir )
    # Needed to support multiple users working on the same machine;
    # see issue 606.
    MakeFolderAccessibleToAll( tempdir )
  except OSError:
    # Folder already exists, skip folder creation.
    pass
  return tempdir


def MakeFolderAccessibleToAll( path_to_folder ):
  current_stat = os.stat( path_to_folder )
  # readable, writable and executable by everyone
  flags = ( current_stat.st_mode | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH
            | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP )
  os.chmod( path_to_folder, flags )


def RunningInsideVim():
  try:
    import vim  # NOQA
    return True
  except ImportError:
    return False


def GetUnusedLocalhostPort():
  sock = socket.socket()
  # This tells the OS to give us any free port in the range [1024 - 65535]
  sock.bind( ( '', 0 ) )
  port = sock.getsockname()[ 1 ]
  sock.close()
  return port


def RemoveIfExists( filename ):
  try:
    os.remove( filename )
  except OSError:
    pass


def Memoize( obj ):
  cache = obj.cache = {}

  @functools.wraps( obj )
  def memoizer( *args, **kwargs ):
    key = str( args ) + str( kwargs )
    if key not in cache:
      cache[ key ] = obj( *args, **kwargs )
    return cache[ key ]
  return memoizer


@Memoize
def PathToPythonInterpreter():
  if not RunningInsideVim():
    return sys.executable

  import vim  # NOQA
  user_path_to_python = vim.eval( 'g:ycm_path_to_python_interpreter' )
  if user_path_to_python:
    return user_path_to_python

  # We check for 'python2' before 'python' because some OS's (I'm looking at you
  # Arch Linux) have made the... interesting decision to point /usr/bin/python
  # to python3.
  python_names = [ 'python2', 'python' ]

  path_to_python = PathToFirstExistingExecutable( python_names )
  if path_to_python:
    return path_to_python

  # On Windows, Python may not be on the PATH at all, so we check some common
  # install locations.
  if OnWindows():
    if os.path.exists( WIN_PYTHON27_PATH ):
      return WIN_PYTHON27_PATH
    elif os.path.exists( WIN_PYTHON26_PATH ):
      return WIN_PYTHON26_PATH
  raise RuntimeError( 'Python 2.7/2.6 not installed!' )


def PathToFirstExistingExecutable( executable_name_list ):
  for executable_name in executable_name_list:
    path = FindExecutable( executable_name )
    if path:
      return path
  return None


# On Windows, distutils.spawn.find_executable only works for .exe files
# but .bat and .cmd files are also executables, so we use our own
# implementation.
def FindExecutable( executable ):
  paths = os.environ[ 'PATH' ].split( os.pathsep )
  base, extension = os.path.splitext( executable )

  if OnWindows() and extension.lower() not in WIN_EXECUTABLE_EXTS:
    extensions = WIN_EXECUTABLE_EXTS
  else:
    extensions = ['']

  for extension in extensions:
    executable_name = executable + extension
    if not os.path.isfile( executable_name ):
      for path in paths:
        executable_path = os.path.join(path, executable_name )
        if os.path.isfile( executable_path ):
          return executable_path
    else:
      return executable_name
  return None


def OnWindows():
  return sys.platform == 'win32'


def OnCygwin():
  return sys.platform == 'cygwin'


def OnMac():
  return sys.platform == 'darwin'


def OnTravis():
  return 'TRAVIS' in os.environ


# From here: http://stackoverflow.com/a/8536476/1672783
def TerminateProcess( pid ):
  if OnWindows():
    import ctypes
    PROCESS_TERMINATE = 1
    handle = ctypes.windll.kernel32.OpenProcess( PROCESS_TERMINATE,
                                                 False,
                                                 pid )
    ctypes.windll.kernel32.TerminateProcess( handle, -1 )
    ctypes.windll.kernel32.CloseHandle( handle )
  else:
    os.kill( pid, signal.SIGTERM )


def AncestorFolders( path ):
  folder = os.path.abspath( path )
  while True:
    parent = os.path.dirname( folder )
    if parent == folder:
      break
    folder = parent
    yield folder


def PathToNearestThirdPartyFolder( path ):
  for folder in AncestorFolders( path ):
    path_to_third_party = os.path.join( folder, 'third_party' )
    if os.path.isdir( path_to_third_party ):
      return path_to_third_party
  return None


def PathToNearestFile( path, filename ):
  for folder in AncestorFolders( path ):
    path_to_filename = os.path.join( folder, filename )
    if os.path.isfile( path_to_filename ):
        return path_to_filename
  return None

def AddNearestThirdPartyFoldersToSysPath( filepath ):
  path_to_third_party = PathToNearestThirdPartyFolder( filepath )
  if not path_to_third_party:
    raise RuntimeError(
        'No third_party folder found for: {0}'.format( filepath ) )

  for folder in os.listdir( path_to_third_party ):
    sys.path.insert( 0, os.path.realpath( os.path.join( path_to_third_party,
                                                        folder ) ) )


def ForceSemanticCompletion( request_data ):
  return ( 'force_semantic' in request_data and
           bool( request_data[ 'force_semantic' ] ) )


# A wrapper for subprocess.Popen that fixes quirks on Windows.
def SafePopen( *args, **kwargs ):
  if OnWindows():
    # We need this to start the server otherwise bad things happen.
    # See issue #637.
    if kwargs.get( 'stdin_windows' ) is subprocess.PIPE:
      kwargs[ 'stdin' ] = subprocess.PIPE
    # Do not create a console window
    kwargs[ 'creationflags' ] = CREATE_NO_WINDOW

  kwargs.pop( 'stdin_windows', None )
  return subprocess.Popen( *args, **kwargs )

