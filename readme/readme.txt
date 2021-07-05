Plugin for CudaText.
Adds widget below editor for quick filesystem navigation.


Configuration
-------------

Plugin can be configured via menu:
"Options > Settings-plugins > Breadcrumbs".

Section [breadcrumbs].
Options description:
* "show_root_parents" - show full path, otherwise - only project-directory files are shown
* "root_dir_source" - project-directory source (accepts comma-separated list of values for fallback):
    * 0 - parent directory of '.cuda-proj'
    * 1 - first directory in project
    * 2 - project main-file's directory
* "file_sort_type" - how files in the tree-dialog are sorted:
	* "name" - sort by filename (default)
	* "ext" - sort by extension
    

Author: halfbrained (https://github.com/halfbrained)

License: MIT
