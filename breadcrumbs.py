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
opt_max_dirs_count    = 0

PROJECT_DIR = None
IS_UNIX     = app_proc(PROC_GET_OS_SUFFIX, '') not in ['', '__mac']
USER_DIR    = os.path.expanduser('~')

SHOW_CODE = False

#CodeItem = namedtuple('CodeItem', 'name icon')

h_tree      = app_proc(PROC_GET_CODETREE, "")
h_im_tree   = tree_proc(h_tree, TREE_GET_IMAGELIST)


def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s=='1'

def get_carets_tree_path():
    if not SHOW_CODE:
        return ()

    def get_caret_node(carets, parent=0): #SKIP
        items = tree_proc(h_tree, TREE_ITEM_ENUM, id_item=parent)
        if items:
            for id_,name in items:
                #print(f'.. checking name:{name}')

                x0,y0, x1,y1 = tree_proc(h_tree, TREE_ITEM_GET_RANGE, id_item=id_)
                if x0 == -1:
                    child_id = get_caret_node(carets, id_)
                    if child_id is not None:
                        #print(f'NOTE: returning -1')
                        return child_id
                    continue

                if all((y0,x0) <= (c[1],c[0]) <= (y1,x1)  and  (c[2] == -1 or (y0,x0) <= (c[3],c[2]) <= (y1,x1))
                                for c in carets):
                    child_id = get_caret_node(carets, id_)
                    return child_id  if child_id is not None else  id_

                child_id = get_caret_node(carets, id_)
                if child_id is not None:
                    return child_id

    carets = ed.get_carets()
    if carets:
        node_id = get_caret_node(carets)

        if node_id:
            #print(f'target tyree node: {(node_id,)}')
            names = []
            id_ = node_id
            while True:
                props = tree_proc(h_tree, TREE_ITEM_GET_PROPS, id_item=id_)
                names.append(props['text'] or '<empty>')

                if not props  or  props['parent'] == 0:
                    break

                id_ = props['parent']

            names.reverse()
            return names
    return ()

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

        self._opened_h_eds = set() # handles for editors that have been `on_open`-ed - to ignore on_focus

        Colors.update()

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
        file_open(fn_config)

    #def on_caret(self, ed_self):
        #self._update(ed_self)

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

        #elif state == APPSTATE_CODETREE_AFTER_FILL:
            #self._update(ed)

    def on_close(self, ed_self):
        h_ed0 = ed_self.get_prop(PROP_HANDLE_PRIMARY)
        h_ed1 = ed_self.get_prop(PROP_HANDLE_SECONDARY)
        self._ed_uis.pop(h_ed0, None)
        self._ed_uis.pop(h_ed1, None)
        self._opened_h_eds.discard(h_ed0)
        self._opened_h_eds.discard(h_ed1)


    def on_cell_click(self, id_dlg, id_ctl, data='', info=''):
        # info: "<cell_ind>:<h_ed>"
        cell_ind, h_ed = map(int, info.split(':'))
        bread = self._ed_uis[h_ed]
        bread.on_click(cell_ind)


    def _update(self, ed_self):
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
                bc0 = Bread(ed_self)
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
                    bc2 = Bread(ed2)
                    self._ed_uis[h_ed2] = bc2

        return (bc0,)  if h_ed2 is None else  (bc0,bc2)

    @property
    def current(self):
        return self._ed_uis.get(ed.get_prop(PROP_HANDLE_SELF))

    def print_breads(self):
        for h_ed,bread in self._ed_uis.items():
            print(f'* bread: {h_ed:_}: {bread.ed}  -  {bread.ed.get_filename()}')



class Bread:

    _tree = None

    def __init__(self, ed_self):
        self.ed = Editor(ed_self.get_prop(PROP_HANDLE_SELF))  if ed_self is ed else  ed_self
        self.fn = self.ed.get_filename()

        self.hparent = None
        self.n_sb = None
        self.h_sb = None

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
        })
        try:
            statusbar_proc(self.h_sb, STATUSBAR_SET_PADDING, value=4) # api=399
            statusbar_proc(self.h_sb, STATUSBAR_SET_SEPARATOR, value='>')
            statusbar_proc(self.h_sb, STATUSBAR_SET_OVERFLOW_LEFT, value=True)
        except NameError:
            pass


    def reset(self):
        self._path_items = []
        self._code_items = []
        statusbar_proc(self.h_sb, STATUSBAR_DELETE_ALL)

    def update(self):
        if not self.fn:
            return

        _old_root = self._root

        path_items = self._get_path_items()
        code_items = get_carets_tree_path()

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
            if old != new  and  new is not None:
                hint = None
                if len(new) > opt_max_name_len:
                    hint = new
                    new = ellipsize(new)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i, value=new)
                _h_ed = self.ed.get_prop(PROP_HANDLE_SELF)
                _callback = "module={};cmd={};info={}:{};".format(
                                        'cuda_breadcrumbs', 'on_cell_click', i, _h_ed)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_CALLBACK, index=i, value=_callback)
                if i == 0  and  self._root:
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_HINT, index=i, value=self._root)
                elif hint is not None:
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_HINT, index=i, value=hint)

        # update changed  CODE  cells
        offset = len(path_items)
        for i,(old,new) in enumerate(zip_longest(self._code_items, code_items)):
            if old != new  and  new is not None:
                new = str(new)
                hint = None
                if len(new) > opt_max_name_len:
                    hint = new
                    new = ellipsize(new)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i+offset, value=new)
                if hint is not None:
                    statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_HINT, index=i, value=hint)
                '!!!'
                # update icons from tree data
                #statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i, value=new)

        self._path_items = path_items
        self._code_items = code_items


    def on_click(self, cell_ind):
        if len(self._path_items) == 1: # no file
            return

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

            btn_rect = self._get_cell_rect(cell_ind)
            _parent = str(path.parent)  if path.parent else  str(path)
            self.tree.show_dir(fn=str(path),  root=_parent,  btn_rect=btn_rect,  h_ed=self.ed.h)

        else:   # if code-item click
            code_ind = cell_ind - len(self._path_items)
            print(f'code clicked: {Path(*self._path_items)} -- {self._code_items[:code_ind+1]}')


    def on_theme(self):
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
        self.fn = self.ed.get_filename()

        if self.fn  and  self.hparent is None:
            self._add_ui()
            self.reset()
            self.on_theme()

        self.update()


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
        elif IS_UNIX  and  opt_tilde_home  and  self.fn.startswith(USER_DIR):
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

        cls.code_bg = colors['TabActive'    ]['color']
        cls.code_fg = colors['TabFontActive']['color']

        cls.border = colors['TabBorderActive']['color']


def set_cell_colors(h_sb, ind, bg, fg):
    statusbar_proc(h_sb, STATUSBAR_SET_CELL_COLOR_BACK, index=ind, value=bg)
    statusbar_proc(h_sb, STATUSBAR_SET_CELL_COLOR_FONT, index=ind, value=fg)

def ellipsize(s):
    _start = opt_max_name_len//2
    _end = opt_max_name_len - _start
    return s[:_start] + '...' + s[-_end:]
