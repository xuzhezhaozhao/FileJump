let s:save_cpo = &cpo
set cpo&vim

function! s:restore_cpo()
  let &cpo = s:save_cpo
  unlet s:save_cpo
endfunction

if exists( "g:loaded_filejump" )
    call s:restore_cpo()
	finish
elseif !has( 'python' )
  echohl WarningMsg |
        \ echomsg "FileJump unavailable: requires Vim compiled with " .
        \ "Python 2.x support" |
        \ echohl None
  call s:restore_cpo()
  finish
endif

if &diff
	finish
endif

let g:loaded_filejump = 1
let s:script_folder_path = escape( expand( '<sfile>:p:h' ), '\' )

let g:user_defined_include_paths = 
	\ get(g:, 'user_defined_include_paths', ['.', 'include/'])
let g:system_defined_include_paths = 
	\ get(g:, 'system_defined_include_paths', ['/usr/include', '/usr/local/include'])

python << EOF
import sys
import vim
import os

script_folder = vim.eval( 's:script_folder_path' )
sys.path.insert( 0, os.path.join( script_folder, '../python' ) )

from filejump import fj_vimsupport
from filejump import fj_utils

# find first valid path in include_paths including filename
def GetHeaderFilename(include_paths, filename):
	for folder in include_paths:
		real_filename = os.path.join( folder, filename )
		if os.path.isfile( real_filename ):
			return real_filename
	return None

# find nearest file naming '.filejump'
def FindUserFileJump():
	current_filename = vim.eval( "expand('%:p')" )
	return fj_utils.PathToNearestFile( current_filename, '.filejump' )

# populate user_defined_include_paths and system_defined_include_paths
# if find .filejump file, use it, otherwise use default settings
def PopulateIncludePaths():
	global user_defined_include_paths, system_defined_include_paths
	user_defined_include_paths = vim.eval('g:user_defined_include_paths')
	system_defined_include_paths = vim.eval('g:system_defined_include_paths')

	user_filejump = FindUserFileJump()
	if not user_filejump:
		return

	user_filejump_dir = os.path.dirname(user_filejump)
	for line in open(user_filejump):
		line = line.strip()
		if line.startswith('-I'):
			path = os.path.join(user_filejump_dir, line[2:].strip())
			user_defined_include_paths.append(path)
		elif line.startswith('-isystem'):
			path = os.path.join(user_filejump_dir, line[8:].strip())
			system_defined_include_paths.append(path)
EOF

" check which mode we use filejump
" -1: normal 
"  0: user #include ""
"  1: system #include <>
function! s:UserOrSystemHeader()
python << EOF
line = fj_vimsupport.CurrentLineContents().strip()
if not line.startswith("#include"):
	vim.command( "return -1" )
pos1 = line.find("\"")
pos2 = line.find("<")
if pos1 != -1:
	vim.command( "return 0" )
elif pos2 != -1:
	vim.command( "return 1" )
else:
	vim.command( "return -1" )
EOF
endfunction

function! s:JumpToFile(filename, buffer_command)
let header_flag = s:UserOrSystemHeader()
python << EOF
header_flag = int(vim.eval('header_flag'))
filename = vim.eval('a:filename')
buffer_command = vim.eval('a:buffer_command')

PopulateIncludePaths()

include_paths = ['.']
if header_flag == 0:
	include_paths = user_defined_include_paths + system_defined_include_paths
elif header_flag == 1:
	include_paths = system_defined_include_paths + user_defined_include_paths

header_filename = GetHeaderFilename(include_paths, filename)

if header_filename:
	fj_vimsupport.JumpToLocation(header_filename, -1, -1, buffer_command)
else:
    vim.command("echohl WarningMsg | echomsg \"FileJump: can't find such file in include path.\" | echohl None")
EOF
endfunction

" just for debug
function! s:DisplayIncludePaths()
python << EOF
print(user_defined_include_paths, system_defined_include_paths)
EOF
endfunction

function! s:FileJump(buffer_command)
	let filename = escape(expand(expand('<cfile>')), ' ')
	call s:JumpToFile(filename, a:buffer_command)
endfunction

command! FileJump call s:FileJump('same_buffer')
command! FileJumpSplit call s:FileJump('horizontal-split')
command! FileJumpVSplit call s:FileJump('vertical-split')
command! FileJumpTabEdit call s:FileJump('new-or-existing-tab')
command! FileJumpDebugInfo call s:DisplayIncludePaths()

" This is basic vim plugin boilerplate
call s:restore_cpo()
