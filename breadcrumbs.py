import os
import sys
from pathlib import Path
#from collections import namedtuple
from itertools import zip_longest

from cudatext import *


"""
#TODO
* update icons
* handle hidden CodeTree
"""

dir_settings = app_path(APP_DIR_SETTINGS)
fn_config    = os.path.join(dir_settings, 'plugins.ini')
OPT_SEC      = 'breadcrumbs'

opt_position_bottom   = True
opt_root_dir_source   = [0]
opt_show_root_parents = True
opt_tilde_home        = True
opt_file_sort_type    = 'name'
opt_show_hidden_files = False
opt_max_name_len      = 25
opt_code_navigation   = 0 # 0=off, 1=fast, 2=good
opt_max_dirs_count    = 0
opt_path_separator    = '' # empty string for os.sep
opt_code_tree_height  = 0 # 0=no change; -1=fullscreen; 1+=pixel height

PROJECT_DIR = None
USER_DIR    = os.path.expanduser('~')

SHOW_BAR = True
SHOW_CODE = False

#CodeItem = namedtuple('CodeItem', 'name icon')

h_tree      = app_proc(PROC_GET_CODETREE, "")


def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s=='1'

def hide_tree(tag='', info=''):
    if Bread._tree:
        Bread._tree.hide()


def get_project_dir():
    """ choose project root directory: .opt_root_dir_source
    """
    if 'cuda_project_man' not in sys.modules:
        return None

    import cuda_project_man

    path = None
    for optval in opt_root_dir_source:
        if optval == 0: # project file dir
            path = cuda_project_man.project_variables()["ProjDir"]
        elif optval == 1: # first node
            _nodes = cuda_project_man.global_project_info.get('nodes')
            path = _nodes[0] if _nodes else None
        elif optval == 2: # project's main-file dir
            path = cuda_project_man.global_project_info.get('mainfile')
            if path:
                path = os.path.dirname(path)

        if path:
            return path


class Command:

    def __init__(self):
        self._load_config()

        self._ed_uis = {} # h_ed -> Bread
        self.is_loading_sesh = False

        self._last_oncaret_time = 0
        self._opened_h_eds = set() # handles for editors that have been `on_open`-ed - to ignore on_focus

        Colors.update()

        # subscribe to events
        _events = 'on_open,on_save,on_state,on_focus'
        if opt_code_navigation:
            _events += ',on_caret'
        _ev_str = 'cuda_breadcrumbs;{};;'.format(_events)
        app_proc(PROC_SET_EVENTS, _ev_str)

    def _load_config(self):
        global PROJECT_DIR
        global opt_position_bottom
        global opt_root_dir_source
        global opt_show_root_parents
        global opt_file_sort_type
        global opt_tilde_home
        global opt_show_hidden_files
        global opt_max_name_len
        global opt_max_dirs_count
        global opt_path_separator
        global opt_code_navigation
        global opt_code_tree_height

        PROJECT_DIR = get_project_dir()

        _root_dir_source_val = ini_read(fn_config, OPT_SEC, 'root_dir_source', '0')
        try:
            opt_root_dir_source = list(map(int, _root_dir_source_val.split(',') ))
        except:
            print('NOTE: Breadcrumbs - Unable to parse option value: "root_dir_source" should be '
                    + 'comma-separated string of integers 0-2')

        opt_position_bottom = str_to_bool(ini_read(fn_config, OPT_SEC, 'position_bottom', '1'))
        opt_show_root_parents = str_to_bool(ini_read(fn_config, OPT_SEC, 'show_root_parents', '1'))
        opt_file_sort_type = ini_read(fn_config, OPT_SEC, 'file_sort_type', opt_file_sort_type)
        opt_tilde_home = str_to_bool(ini_read(fn_config, OPT_SEC, 'tilde_home', '1'))
        opt_show_hidden_files = str_to_bool(ini_read(fn_config, OPT_SEC, 'show_hidden_files', '0'))
        opt_max_name_len = int(ini_read(fn_config, OPT_SEC, 'max_name_len', str(opt_max_name_len)))
        opt_max_dirs_count = int(ini_read(fn_config, OPT_SEC, 'max_dirs_count', str(opt_max_dirs_count)))
        opt_path_separator = ini_read(fn_config, OPT_SEC, 'path_separator', opt_path_separator)
        opt_code_navigation = int(ini_read(fn_config, OPT_SEC, 'code_navigation', str(opt_code_navigation)))
        opt_code_tree_height = int(ini_read(fn_config, OPT_SEC, 'code_tree_height', str(opt_code_tree_height)))

        if opt_code_navigation not in {0,1,2}:
            opt_code_navigation = 0

    def config(self):
        _root_dir_source_str = ','.join(map(str, opt_root_dir_source))
        ini_write(fn_config, OPT_SEC, 'position_bottom',    bool_to_str(opt_position_bottom) )
        ini_write(fn_config, OPT_SEC, 'root_dir_source',    _root_dir_source_str)
        ini_write(fn_config, OPT_SEC, 'show_root_parents',  bool_to_str(opt_show_root_parents) )
        ini_write(fn_config, OPT_SEC, 'file_sort_type',     opt_file_sort_type)
        ini_write(fn_config, OPT_SEC, 'tilde_home',         bool_to_str(opt_tilde_home) )
        ini_write(fn_config, OPT_SEC, 'show_hidden_files',  bool_to_str(opt_show_hidden_files) )
        ini_write(fn_config, OPT_SEC, 'max_name_len',       str(opt_max_name_len) )
        ini_write(fn_config, OPT_SEC, 'max_dirs_count',     str(opt_max_dirs_count) )
        ini_write(fn_config, OPT_SEC, 'path_separator',     opt_path_separator)
        ini_write(fn_config, OPT_SEC, 'code_navigation',    str(opt_code_navigation) )
        ini_write(fn_config, OPT_SEC, 'code_tree_height',     str(opt_code_tree_height) )
        file_open(fn_config)

    def on_caret(self, ed_self):
        _callback = "module=cuda_breadcrumbs;cmd=_update_callblack;"
        timer_proc(TIMER_START_ONE, _callback, 500, tag=str(ed_self.h))


    def on_open(self, ed_self):
        self._opened_h_eds.add(ed_self.get_prop(PROP_HANDLE_PRIMARY))
        self._opened_h_eds.add(ed_self.get_prop(PROP_HANDLE_SECONDARY))

        if not self.is_loading_sesh:
            breads = self._get_breads(ed_self, check_files=True)
            for b in breads:
                b.on_fn_change()

    def on_save(self, ed_self):
        breads = self._get_breads(ed_self)
        for b in breads:
            b.on_fn_change()

    def on_focus(self, ed_self):
        if ed_self.h not in self._opened_h_eds:
            return # ignore `on_focus` that happens before `on_open`

        if ed_self.get_prop(PROP_HANDLE_SELF) not in self._ed_uis:  # need for lazy bread-injection
            self._update(ed_self)


    def on_state(self, ed_self, state):
        # tree changed
        if state == APPSTATE_THEME_UI:
            Colors.update()
            for bread in self._ed_uis.values():
                bread.on_theme()

        # session loading start
        elif state == APPSTATE_SESSION_LOAD_BEGIN: # started
            self.is_loading_sesh = True
        elif state in [APPSTATE_SESSION_LOAD_FAIL, APPSTATE_SESSION_LOAD]: # ended
            self.is_loading_sesh = False

            visible_eds = (ed_group(i)  for i in range(9))
            for edt in filter(None, visible_eds):
                self.on_open(edt)

        elif state == APPSTATE_PROJECT:
            global PROJECT_DIR

            new_project_dir = get_project_dir()
            if PROJECT_DIR != new_project_dir:
                PROJECT_DIR = new_project_dir
                for bread in self._ed_uis.values():
                    bread.update()

        elif state == APPSTATE_CODETREE_AFTER_FILL:
            if opt_code_navigation:
                _callback = "module=cuda_breadcrumbs;cmd=_update_callblack;"
                _h_ed = ed.get_prop(PROP_HANDLE_SELF)
                timer_proc(TIMER_START_ONE, _callback, 500, tag=str(_h_ed))


    def on_close(self, ed_self):
        h_ed0 = ed_self.get_prop(PROP_HANDLE_PRIMARY)
        h_ed1 = ed_self.get_prop(PROP_HANDLE_SECONDARY)
        b0 = self._ed_uis.pop(h_ed0, None)
        b1 = self._ed_uis.pop(h_ed1, None)
        self._opened_h_eds.discard(h_ed0)
        self._opened_h_eds.discard(h_ed1)

        for b in filter(None, (b0,b1)):
            b.on_close()


    def on_cell_click(self, id_dlg, id_ctl, data='', info=''):
        # info: "<cell_ind>:<h_ed>"
        cell_ind, h_ed = map(int, info.split(':'))
        bread = self._ed_uis[h_ed]
        bread.on_click(cell_ind)

    # cmd
    def toggle_vis(self):
        global SHOW_BAR

        SHOW_BAR = not SHOW_BAR

        for bread in self._ed_uis.values():
            bread.set_visible(SHOW_BAR)

        if SHOW_BAR:  # show
            visible_eds = (ed_group(i)  for i in range(9))
            for edt in filter(None, visible_eds):
                if edt.h not in self._ed_uis:
                    self.on_open(edt)

    # cmd
    def show_tree(self):
        breads = self._get_breads(ed)
        breads[0].show_file_tree()


    def _update_callblack(self, tag='', info=''):
        h_ed = int(tag)
        if h_ed == ed.get_prop(PROP_HANDLE_SELF):
            self._update(ed)


    def _update(self, ed_self):
        if not SHOW_BAR:
            return

        breads = self._get_breads(ed_self)
        for b in breads:
            b.update()

    def _get_breads(self, ed_self, check_files=False):
        """ returns tuple of Breads in tab; usually one,  two on split tab with two files
        """
        h_ed = ed_self.get_prop(PROP_HANDLE_SELF)

        _h_ed0 = ed_self.get_prop(PROP_HANDLE_PRIMARY)
        _h_ed1 = ed_self.get_prop(PROP_HANDLE_SECONDARY)
        h_ed2 = _h_ed0  if h_ed == _h_ed1 else  _h_ed1

        bc0 = self._ed_uis.get(h_ed)
        if bc0 is None:
            # check if Bread for sibling-Editor exists and is same file -- reuse
            bc2 = self._ed_uis.get(h_ed2)
            if bc2 is not None:
                fn =  ed_self.get_filename()
                if fn == Editor(h_ed2).get_filename()  and  fn is not None: # both Editors - same file
                    bc0 = bc2
                    self._ed_uis[h_ed] = bc2
                    h_ed2 = None # dont add second bread if single file

            if bc0 is None: # need new bread
                bc0 = Bread(ed_self, SHOW_BAR)
                self._ed_uis[h_ed] = bc0

        # process secondary editor
        if h_ed2 is not None:
            bc2 = self._ed_uis.get(h_ed2)
            if bc2 is None  or  (check_files  and  bc2 is bc0):
                ed2 = Editor(h_ed2)
                fn0,fn2 = ed_self.get_filename(),  ed2.get_filename()
                # if two editors are the same file - need only one bread,  two files - two breads
                if fn0 == fn2  and  fn0 is not None:
                    self._ed_uis[h_ed2] = bc0 # point both editors to the same Bread
                    h_ed2 = None    # -- same file - dont add second ed to result
                else:
                    bc2 = Bread(ed2, SHOW_BAR)
                    self._ed_uis[h_ed2] = bc2
            elif bc2 is bc0:
                h_ed2 = None

        return (bc0,)  if h_ed2 is None else  (bc0,bc2)

    @property
    def current(self):
        return self._ed_uis.get(ed.get_prop(PROP_HANDLE_SELF))

    def print_breads(self):
        for h_ed,bread in self._ed_uis.items():
            print(f'* bread: {h_ed:_}: {bread.ed}  -  {bread.ed.get_filename()}')



class Bread:

    _tree = None

    def __init__(self, ed_self, is_visible):
        self.ed = Editor(ed_self.get_prop(PROP_HANDLE_SELF))  if ed_self is ed else  ed_self
        self.fn = self.ed.get_filename(options="*")
        self.is_visible = is_visible


        self.hparent = None
        self.n_sb = None
        self.h_sb = None
        self.h_im = None

        self._root = None
        self._path_items = []
        self._code_items = []

        if self.fn:
            self._add_ui()
            self.reset()
            self.on_theme()

    @property
    def tree(self):
        if Bread._tree is None:

            from .dlg import TreeDlg

            Bread._tree = TreeDlg(opts={
                'sort_type':         opt_file_sort_type,
                'show_hidden_files': opt_show_hidden_files,
                'position_bottom':   opt_position_bottom,
                'code_tree_height':  opt_code_tree_height,
            })
        return Bread._tree

    def _add_ui(self):
        self.hparent = self.ed.get_prop(PROP_HANDLE_PARENT)
        self.n_sb    = dlg_proc(self.hparent, DLG_CTL_ADD, 'statusbar')
        self.h_sb    = dlg_proc(self.hparent, DLG_CTL_HANDLE, index=self.n_sb)

        _align = ALIGN_BOTTOM  if opt_position_bottom else  ALIGN_TOP
        dlg_proc(self.hparent, DLG_CTL_PROP_SET, index=self.n_sb, prop={
            'color': Colors.bg,
            'align': _align,
            'vis': self.is_visible,
        })
        statusbar_proc(self.h_sb, STATUSBAR_SET_PADDING, value=4) # api=399
        _sep = opt_path_separator  or  os.sep
        statusbar_proc(self.h_sb, STATUSBAR_SET_SEPARATOR,     value=_sep)
        statusbar_proc(self.h_sb, STATUSBAR_SET_OVERFLOW_LEFT, value=True)


    def reset(self):
        self._path_items = []
        self._code_items = []
        statusbar_proc(self.h_sb, STATUSBAR_DELETE_ALL)

    def set_visible(self, vis):
        self.is_visible = vis
        if self.hparent is not None:
            dlg_proc(self.hparent, DLG_CTL_PROP_SET, index=self.n_sb, prop={'vis': vis})


    def update(self):
        if not self.fn:
            return

        if opt_code_navigation != 0  and  self.h_im is None:
            h_im = tree_proc(h_tree, TREE_GET_IMAGELIST)
            if h_im:
                self.h_im = h_im
                statusbar_proc(self.h_sb, STATUSBAR_SET_IMAGELIST, value=self.h_im)

        _old_root = self._root

        path_items = self._get_path_items()
        code_items = CodeTree.get_carets_tree_path(self.ed)
        code_icons = CodeTree.get_icons()

        root_changed = self._root != _old_root

        # no changes
        if not root_changed  and  self._path_items == path_items  and  self._code_items == code_items:
            return

        if root_changed \
                or len(self._path_items) != len(path_items) \
                or len(self._code_items) != len(code_items):
            if opt_show_root_parents  and  PROJECT_DIR  and  self.fn.startswith(PROJECT_DIR):
                _n_prefix = len(Path(PROJECT_DIR).parent.parts)
            else:
                _n_prefix = 0
            self._update_bgs(len(path_items),  len(code_items),  _n_prefix)

        # update changed  PATH  cells
        for i,(old,new) in enumerate(zip_longest(self._path_items, path_items)):
            if old != new:
                if new is not None:
                    hint = None
                    if len(new) > opt_max_name_len+1:
                        hint = new
                        new = ellipsize(new)
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i, value=new)
                    _callback = "module={};cmd={};info={}:{};".format(
                                            'cuda_breadcrumbs', 'on_cell_click', i, self.ed.h)
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_CALLBACK, index=i, value=_callback)
                    if i == 0  and  self._root:
                        statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_HINT, index=i, value=self._root)
                    elif hint is not None:
                        statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_HINT, index=i, value=hint)
                elif old is None: # was not path cell, but code-path
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_IMAGEINDEX, index=i, image_index=-1)

        # update changed  CODE  cells
        offset = len(path_items)
        for i,(old,new,ic_ind) in enumerate(zip_longest(self._code_items, code_items,code_icons)):
            if old != new  and  new is not None:
                hint = None
                if len(new) > opt_max_name_len+1:
                    hint = new
                    new = ellipsize(new)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i+offset, value=new)
                if hint is not None:
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_HINT, index=i, value=hint)
                _callback = "module={};cmd={};info={}:{};".format(
                                        'cuda_breadcrumbs', 'on_cell_click', i+offset, self.ed.h)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_CALLBACK, index=i+offset, value=_callback)
                # update icons from tree data
                if opt_code_navigation != 0  and  self.h_im is not None:
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_IMAGEINDEX, index=i+offset, value=ic_ind)

        self._path_items = path_items
        self._code_items = code_items


    def on_click(self, cell_ind):
        #if len(self._path_items) == 1: # no file
            #return

        self.ed.focus()    # focus editor of clicked breadcrumbs-cell, so `ed` is proper Editor

        # if path-item click
        if cell_ind < len(self._path_items):
            path = Path(*self._path_items[:cell_ind+1])
            if self._root:
                # add project root if is hidden
                if not opt_show_root_parents  and  self._root == PROJECT_DIR:
                    path = Path(self._root).parent / path
                elif opt_tilde_home  and  self._root == USER_DIR:
                    path = Path(self._root) / path.relative_to('~')
                elif self._root:
                    path = Path(self._root) / path

            if self.is_visible:
                btn_rect = self._get_cell_rect(cell_ind)
            else:
                cursor_xy = app_proc(PROC_GET_MOUSE_POS, '')
                btn_rect = (*cursor_xy, 0, 0)

            # highligh clicked cell
            _cmd = STATUSBAR_SET_CELL_COLOR_LINE2 if opt_position_bottom else STATUSBAR_SET_CELL_COLOR_LINE
            statusbar_proc(self.h_sb, _cmd, index=cell_ind, value=Colors.hover_bg)

            _parent = str(path.parent)  if path.parent else  str(path)
            self.tree.show_dir(
                    fn       = str(path),
                    root     = _parent,
                    btn_rect = btn_rect,
                    h_ed     = self.ed.h,
                    on_hide  = lambda cell_ind=cell_ind: self._clear_cell_lines(cell_ind),
            )

        else:   # if code-item click
            _code_ind = cell_ind - len(self._path_items)
            _code_path_items = self._code_items[:_code_ind+1]
            #print(f'code clicked: {Path(*self._path_items)} -- {_code_path_items}')

            # highligh clicked cell
            _cmd = STATUSBAR_SET_CELL_COLOR_LINE2 if opt_position_bottom else STATUSBAR_SET_CELL_COLOR_LINE
            statusbar_proc(self.h_sb, _cmd, index=cell_ind, value=Colors.hover_bg)

            _btn_rect = self._get_cell_rect(cell_ind)
            _on_hide = lambda cell_ind=cell_ind: self._clear_cell_lines(cell_ind)
            self.tree.show_code(_code_path_items, _btn_rect, h_ed=self.ed.h, on_hide=_on_hide)

    def show_file_tree(self):
        self.on_fn_change()
        if self.fn:
            self.on_click(len(self._path_items) - 1)
        else:
            msg_status('Current document is not a file')


    def on_theme(self):
        if self.hparent is None:
            return

        dlg_proc(self.hparent, DLG_CTL_PROP_SET, index=self.n_sb, prop={ 'color': Colors.bg })

        n_path = len(self._path_items)
        for i in range(n_path): # path cell colors
            set_cell_colors(self.h_sb, i, bg=Colors.path_bg, fg=Colors.path_fg)

        _code_inds = range(n_path, n_path+len(self._code_items))
        for i in _code_inds:    # code cell colors
            set_cell_colors(self.h_sb, i, bg=Colors.path_bg, fg=Colors.path_fg)

        statusbar_proc(self.h_sb, STATUSBAR_SET_COLOR_BORDER_R, value=Colors.border)
        if opt_position_bottom:
            statusbar_proc(self.h_sb, STATUSBAR_SET_COLOR_BORDER_TOP, value=Colors.border)
        else:
            try: # new api
                statusbar_proc(self.h_sb, STATUSBAR_SET_COLOR_BORDER_BOTTOM, value=Colors.border)
            except NameError:
                pass

    def on_fn_change(self):
        self.fn = self.ed.get_filename(options="*")

        if self.fn  and  self.hparent is None:
            self._add_ui()
            self.reset()
            self.on_theme()

        self.update()


    def on_close(self):
        self.hparent = None
        self.n_sb = None
        self.h_sb = None

    def _update_bgs(self, n_path, n_code, n_prefix):
        _old_n_path = len(self._path_items)  if self._path_items else  0
        _old_n_code = len(self._code_items)  if self._code_items else  0
        old_n_total = _old_n_path + _old_n_code

        new_n_total = n_path + n_code

        # fix cell count
        if new_n_total  >  old_n_total:     # too few
            for i in range(new_n_total - old_n_total):
                ind = statusbar_proc(self.h_sb, STATUSBAR_ADD_CELL)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_AUTOSIZE, index=ind, value=True)

        elif new_n_total  <  old_n_total:   # too many
            for i in range(old_n_total - new_n_total):
                statusbar_proc(self.h_sb, STATUSBAR_DELETE_CELL, index=new_n_total)

        for i in range(n_path): # update path cells bg+fg
            _bg = Colors.path_bg  if not opt_show_root_parents or i >= n_prefix else  Colors.path_bg_root_parents
            set_cell_colors(self.h_sb, i, bg=_bg, fg=Colors.path_fg)

        for i in range(n_path, n_path+n_code): # update code cells bg+fg
            set_cell_colors(self.h_sb, i, bg=Colors.code_bg, fg=Colors.code_fg)


    def _clear_cell_lines(self, cell_ind):
        if self.hparent is not None:
            _cell_ind_present = cell_ind < statusbar_proc(self.h_sb, STATUSBAR_GET_COUNT)
            if _cell_ind_present:
                for line_cmd in (STATUSBAR_SET_CELL_COLOR_LINE, STATUSBAR_SET_CELL_COLOR_LINE2):
                    statusbar_proc(self.h_sb, line_cmd, index=cell_ind, value=COLOR_NONE)


    def _get_cell_rect(self, ind):
        """ returns screen coords: x,y, w,h
        """
        p = dlg_proc(self.hparent, DLG_CTL_PROP_GET, index=self.n_sb)
        x,y, w,h = p['x'],p['y'], p['w'], p['h'] # local statusbar coords
        sb_screen_coords = dlg_proc(self.hparent, DLG_COORD_LOCAL_TO_SCREEN, index=x, index2=y)

        r = statusbar_proc(self.h_sb, STATUSBAR_GET_CELL_RECT, index=ind)
        return (
            sb_screen_coords[0]+max(0, r[0]), # x
            sb_screen_coords[1],              # y
            r[2]-max(0, r[0]),  # w
            h,                  # h
        )


    def _get_path_items(self):
        ### if need to hide project parents
        if not opt_show_root_parents  and  PROJECT_DIR  and  self.fn.startswith(PROJECT_DIR):
            self._root = PROJECT_DIR
            _root = Path(self._root)
            path_items = Path(self.fn).relative_to(_root.parent).parts

        ### if need to collapse home-dir
        elif opt_tilde_home  and  self.fn.startswith(USER_DIR + os.sep):
            self._root = USER_DIR
            _root = Path(self._root)
            path_items = ('~',) + Path(self.fn).relative_to(_root).parts

        elif self.fn.startswith('/'):
            self._root = '/'
            _root = Path(self._root)
            path_items = Path(self.fn).relative_to(_root).parts

        ### full path
        else:
            self._root = None
            path_items = Path(self.fn).parts

        # limit path-cells count (OPT: `opt_max_dirs_count`)
        if opt_max_dirs_count > 0:
            n_items = len(path_items)
            if (n_items > opt_max_dirs_count + 1
                    # if extra is just a single `~` - allow
                    and  not (n_items == opt_max_dirs_count+2  and  path_items[0] == '~') ):
                _items = Path(self.fn).parts
                _n_endcut = opt_max_dirs_count + 1 #+1 is file-name
                cut, path_items = _items[:-_n_endcut], path_items[-_n_endcut:]
                self._root = str(Path(*cut))

        return path_items


class Colors:
    @classmethod
    def update(cls):
        colors = app_proc(PROC_THEME_UI_DICT_GET, '')

        cls.bg      = colors['EdTextBg'     ]['color']

        cls.path_bg = colors['TabBg'        ]['color']
        cls.path_fg = colors['TabFont'      ]['color']
        cls.path_bg_root_parents = colors['SideBg']['color']

        #cls.code_bg = colors['TabActive'    ]['color']
        r,g,b = cls.path_bg&0xff, (cls.path_bg>>8)&0xff, (cls.path_bg>>16)&0xff
        offset = 12
        if r+g+b < (0xff-offset)<<16:
            r,g,b = min(0xff, r+offset), min(0xff, g+offset), min(0xff, b+offset)
        else:
            r,g,b = max(0, r-offset), max(0, g-offset), max(0, b-offset)
        cls.code_bg = r | (g<<8) | (b<<16)
        _code_fg = colors['TabFontActive']['color']
        cls.code_fg = cls.path_fg  if _code_fg == COLOR_NONE else  _code_fg

        cls.border = colors['TabBorderActive']['color']

        cls.hover_bg = colors['ButtonBgOver']['color']


class CodeTree:
    # local tree if Code-Tree is hidden
    _h = None
    _h_tree = None

    _h_active_tree = None

    _last_icons = ()

    @classmethod
    def get_carets_tree_path(cls, ed_self):
        if not opt_code_navigation:
            return ()

        cls._h_active_tree = None
        cls.ed = ed_self
        cls._last_icons = ()

        carets = cls.ed.get_carets()
        if carets:
            target_pos = (carets[0][1], carets[0][0])  # y0,x0
            node_id = cls._get_caret_node(target_pos)

            if node_id:
                #print(f'target tyree node: {(node_id,)}')
                names,icons = [],[]
                id_ = node_id
                while True:
                    props = tree_proc(cls._h_active_tree, TREE_ITEM_GET_PROPS, id_item=id_)
                    names.append(props['text'] or '<empty>')
                    icons.append(props['icon'])

                    if not props  or  props['parent'] == 0:
                        break

                    id_ = props['parent']

                icons.reverse()
                cls._last_icons = icons

                names.reverse()
                return names
        return ()

    @classmethod
    def get_icons(cls):
        """get icons for last list of names"""
        return cls._last_icons

    @classmethod
    def _get_caret_node(cls, target_pos):
        """ ? items can be missing a range  (x0 == -1 ...)
            ? range might only have start position (x0,y0)
            `target_pos` - (y0,x0) !!! REVERSED
            Get a list of candidate range-starts,  bisect it to search for best match
        """

        def scan_tree_item(target_pos, results, parent=0): #SKIP
            items = cls._get_tree_items(cls._h_active_tree, parent)
            if not items:
                return None

            res = cls.bisect_codetreet(items, target_pos)
            if res is None:     # have missing range in current `items` -> scan every item
                for id_,name in items:
                    scan_tree_item(target_pos, results, parent=id_)
            else:   # found matching range
                id_ = res[1]
                scan_tree_item(target_pos, results, parent=id_)
                results.append(res)
        #end scan_tree_item

        def scan_whole_tree(target_pos, results, parent=0): #SKIP
            items = cls._get_tree_items(cls._h_active_tree, parent)
            if items:
                for p in items:
                    id_,name = p['id'], p['text']
                    range_ = tree_proc(cls._h_active_tree, TREE_ITEM_GET_RANGE, id_item=id_)
                    if range_[0] != -1:
                        results.append((range_, id_))
                    if p['sub_items']:
                        scan_whole_tree(target_pos, results, parent=id_)
        #end scan_whole_tree


        results = []
        if opt_code_navigation == 1: # fast
            scan_tree_item(target_pos, results)     # fills `results`
        elif opt_code_navigation == 2:
            scan_whole_tree(target_pos, results)     # fills `results`

        # look for closest match
        if results:
            best = None
            best_pos = None
            for m in results:
                mpos = (m[0][1], m[0][0])
                if best is None  or  (mpos <= target_pos  and  mpos > best_pos):
                    best = m
                    best_pos = mpos
            return best[1] # -- id_item


    @classmethod
    # modified;  original: bisect_right - https://github.com/python/cpython/blob/3.9/Lib/bisect.py
    def bisect_codetreet(cls, a, x):
        """ returns closest item: (range, item_id)
        """
        # `a`: list((id_, name))
        lo = 0
        hi = len(a)
        while lo < hi:
            mid = (lo+hi)//2

            range_ = tree_proc(cls._h_active_tree, TREE_ITEM_GET_RANGE, id_item=a[mid][0]) # x0,y0, x1,y1
            if range_[0] == -1:
                #print(f'NOTE: nore result: {a[mid]}')
                return None

            _a = (x, lo,hi)
            mid_val = (range_[1], range_[0]) # (start_y, start_x)
            if x < mid_val:
                hi = mid
            else:
                lo = mid+1

        if lo == 0:
            return None
        range_ = tree_proc(cls._h_active_tree, TREE_ITEM_GET_RANGE, id_item=a[lo-1][0])
        return range_, a[lo-1][0]


    @classmethod
    def _get_tree_items(cls, _h_tree, parent=0):
        if parent == 0:   # only check on initial call   (not for recursive calls)
            pan_vis = app_proc(PROC_SHOW_SIDEPANEL_GET, '')         # sidepanel is visible
            if pan_vis  and  app_proc(PROC_SIDEPANEL_GET,'') == 'Code tree':   # sidepanel is Code-Tree
                _h_tree = h_tree
            # code tree is not visible
            else:
                if cls._h is None:
                    cls._h = dlg_proc(0, DLG_CREATE)
                    _n = dlg_proc(cls._h, DLG_CTL_ADD, 'treeview')
                    cls._h_tree = dlg_proc(cls._h, DLG_CTL_HANDLE, index=_n)

                _h_tree = cls._h_tree
                cls.ed.action(EDACTION_CODETREE_FILL, _h_tree)   # fill local tree

        if opt_code_navigation == 1:
            items = tree_proc(_h_tree, TREE_ITEM_ENUM, id_item=parent)
        elif opt_code_navigation == 2:
            items = tree_proc(_h_tree, TREE_ITEM_ENUM_EX, id_item=parent)

        cls._h_active_tree = _h_tree
        return items


def set_cell_colors(h_sb, ind, bg, fg):
    statusbar_proc(h_sb, STATUSBAR_SET_CELL_COLOR_BACK, index=ind, value=bg)
    statusbar_proc(h_sb, STATUSBAR_SET_CELL_COLOR_FONT, index=ind, value=fg)

def ellipsize(s):
    _start = opt_max_name_len//2
    _end = opt_max_name_len - _start
    return s[:_start] + '...' + s[-_end:]
