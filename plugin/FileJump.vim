let s:save_cpo = &cpo
set cpo&vim

if exists( "g:loaded_filejump" )
	finish
endif
if &diff
	finish
endif
let g:loaded_filejump = 1
let s:script_folder_path = escape( expand( '<sfile>:p:h' ), '\' )

let g:user_defined_include_paths = 
	\ get(g:, 'user_defined_include_paths', ['.'])
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

def GetHeaderFilename(include_paths, filename):
	for folder in include_paths:
		real_filename = os.path.join( folder, filename )
		if os.path.isfile( real_filename ):
			return real_filename
	return None

def FindConfFilename(conf_filename):
	current_filename = vim.eval( "expand('%:p')" )
	return fj_utils.PathToNearestFilename( current_filename, conf_filename )

def PopulateIncludePaths():
	global user_defined_include_paths, system_defined_include_paths
	user_defined_include_paths = vim.eval('g:user_defined_include_paths')
	system_defined_include_paths = vim.eval('g:system_defined_include_paths')

	conf_filename = FindConfFilename('.filejump')
	if not conf_filename:
		return

	conf_dir = os.path.dirname(conf_filename)
	for line in open(conf_filename):
		line = line.strip()
		if line.startswith('-I'):
			path = os.path.join(conf_dir, line[2:].strip())
			user_defined_include_paths.append(path)
		elif line.startswith('-isystem'):
			path = os.path.join(conf_dir, line[8:].strip())
			system_defined_include_paths.append(path)
EOF

function! s:JumpToFile(filename)
python << EOF
filename = vim.eval('a:filename')
user = True
user_defined_include_paths = vim.eval('g:user_defined_include_paths')
system_defined_include_paths = vim.eval('g:system_defined_include_paths')

PopulateIncludePaths()

include_paths = []
if user:
	include_paths = user_defined_include_paths + system_defined_include_paths;
else:
	include_paths = system_defined_include_paths + user_defined_include_paths;

real_filename = GetHeaderFilename(include_paths, filename)

if real_filename:
	fj_vimsupport.JumpToLocation(real_filename, 1, 0)
else:
    vim.command("echohl WarningMsg | echomsg \"FileJump: No such file.\" | echohl None")
EOF
endfunction

function! s:DisplayIncludePaths()
python << EOF
print(user_defined_include_paths, system_defined_include_paths)
EOF
endfunction

function! s:FileJump()
	let filename = escape(expand(expand('<cfile>')), ' ')
	call s:JumpToFile(filename)
endfunction

command! FileJump call s:FileJump()
command! FileJumpDebugInfo call s:DisplayIncludePaths()

let &cpo = s:save_cpo
unlet s:save_cpo
