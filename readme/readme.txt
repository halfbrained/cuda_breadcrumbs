Plugin for CudaText.
Shows the toolbar widget (modern name is breadcrumb bar) below or on top of the editor for quick
file-system navigation. For example, when you have active editor with filename
"~/mydir/myfile.ext" ("~" is Unix shortcut for "/home/user"), the widget shows buttons:
[ home > user > mydir > myfile.ext ]
It can also show the "~" button (by option):
[ ~ > mydir > myfile.ext ]

Clicking on each button shows the popup with file-system listing, showing the
folder containing  the clicked item. This popup supports basic tree-view navigation,
you can click files there to open them in CudaText.


Configuration
-------------

Plugin can be configured via menu:
"Options > Settings-plugins > Breadcrumbs".

Section [breadcrumbs].
Options description:
* "position_bottom" - whether to show breadcrumbs below the document, or on top
* "show_root_parents" - show full path, otherwise - only project-directory files are shown
* "root_dir_source" - project-directory source (accepts comma-separated list of values for fallback):
    * 0 - parent directory of '.cuda-proj'
    * 1 - first directory in project
    * 2 - project main-file's directory
* "file_sort_type" - how files in the tree-dialog are sorted:
	* "name" - sort by filename (default)
	* "ext" - sort by extension
* "tilde_home" - replace home directory path by a single item: `~`
* "show_hidden_files" - whether to show hidden files in tree-dialog (hidden by default)
* "max_name_len" - max file/directory name length on breadcrumbs bar
* "max_dirs_count" - limit number of directories displayed on breadcrumbs bar
* "path_separator" - breadcrumbs path separator (by default - OS path separator)
    

Author: halfbrained (https://github.com/halfbrained)

License: MIT
