import os
import json
from pathlib import Path

from cudatext import *

"""
#TODOs
* search
"""

IS_WIN = app_proc(PROC_GET_OS_SUFFIX, '') == ''

VK_ENTER = 13
VK_ESCAPE = 27
VK_SPACE = 0x20
FILE_ATTRIBUTE_HIDDEN = 2 # stat.FILE_ATTRIBUTE_HIDDEN (for windows)


DLG_W = 250
DLG_H = 400
CODE_TREE_H = DLG_H


SORT_TYPE = 'name'
SORT_REVERSE = False
SHOW_HIDDEN_FILES = False
POSITION_BOTTOM = True


def lock_tree(meth):

    def f(*args, **vargs):
        self = args[0]
        if self.h_tree is not None:
            tree_proc(self.h_tree, TREE_LOCK)

        try:
            return meth(*args, **vargs)
        finally:
            if self.h_tree is not None:
                tree_proc(self.h_tree, TREE_UNLOCK)

    return f


class TreeDlg:
    MODE_NONE = 10
    MODE_FILE = 11
    MODE_CODE = 12

    def __init__(self, opts=None):
        global SORT_TYPE
        global SHOW_HIDDEN_FILES
        global POSITION_BOTTOM
        global CODE_TREE_H

        self.h = None
        self.h_tree = None
        self.h_ed = None
        self.data = None
        self.id_map = {} # tree id -> `Node`

        _h_codetree = app_proc(PROC_GET_CODETREE, "")
        self.h_im_file = None
        self.h_im_code = tree_proc(_h_codetree, TREE_GET_IMAGELIST)

        self.is_busy = False

        self._mode = self.MODE_NONE

        self._on_hide = None

        if opts:
            SORT_TYPE         = opts.get('sort_type',         SORT_TYPE)
            SHOW_HIDDEN_FILES = opts.get('show_hidden_files', SHOW_HIDDEN_FILES)
            POSITION_BOTTOM   = opts.get('position_bottom',   POSITION_BOTTOM)
            CODE_TREE_H       = opts.get('code_tree_height',  CODE_TREE_H)


    def init_form(self):
        h = dlg_proc(0, DLG_CREATE)

        colors = app_proc(PROC_THEME_UI_DICT_GET, '')
        color_form_bg = colors['TabBg']['color']

        ###### FORM #######################
        dlg_proc(h, DLG_PROP_SET, prop={
                'cap': 'BreadCrumbs Tree',
                'w': DLG_W, 'h': DLG_H,
                'color': color_form_bg,
                'border': DBORDER_NONE,
                'keypreview': True,
                'topmost': True,
                'on_key_down': self._on_key,
                'on_deact': self.on_deact,
                'on_hide': self.on_hide,
                })

        # tree ##########################
        n = dlg_proc(h, DLG_CTL_ADD, 'treeview')
        dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': 'tree',
                'align': ALIGN_CLIENT,
                'sp_a': 1,
                'on_change': self.tree_on_click,
                'on_click_dbl': self.tree_on_click_dbl,
                })
        self.h_tree = dlg_proc(h, DLG_CTL_HANDLE, index=n)
        tree_proc(self.h_tree, TREE_THEME)

        # init icons
        self.h_im_file = tree_proc(self.h_tree, TREE_GET_IMAGELIST)
        FileIcons.init(self.h_im_file)

        return h


    def show_dir(self, fn, root, btn_rect, h_ed, on_hide=None):
        """ btn_rect - screen (x,y, w,h) rect of button where tree should be shown
        """
        timer_proc(TIMER_STOP, 'module=cuda_breadcrumbs;func=hide_tree;', 0)
        if self._on_hide:
            self._on_hide()

        fn, root = Path(fn), Path(root)
        self._mode = self.MODE_FILE
        self._setup_tree(h_ed, on_hide, btn_rect)

        dlg_proc(self.h, DLG_SHOW_NONMODAL)

        try:
            self.is_busy = True
            app_idle(True)
        finally:
            self.is_busy = False

        self.data = load_filepath_tree(fn, root)

        self._fill_tree( self.data.children )

        # select `fn` tree item
        _rel_path = fn.relative_to(root)
        sel_item = get_data_item(_rel_path.parts,  self.data)
        if sel_item  and  sel_item.parent:
            tree_proc(self.h_tree, TREE_ITEM_SELECT, id_item=sel_item.id)


    def show_code(self, path_items, btn_rect, h_ed, on_hide=None):
        timer_proc(TIMER_STOP, 'module=cuda_breadcrumbs;func=hide_tree;', 0)
        if self._on_hide:
            self._on_hide()

        self._mode = self.MODE_CODE
        self._setup_tree(h_ed, on_hide, btn_rect)

        dlg_proc(self.h, DLG_SHOW_NONMODAL)

        try:
            self.is_busy = True
            app_idle(True)
        finally:
            self.is_busy = False

        # fill tree from active Editor
        edt = Editor(self.h_ed)
        edt.action(EDACTION_CODETREE_FILL, self.h_tree)

        # select `fn` tree item
        target_id = self._get_tree_id(path_items)
        if target_id is not None:
            tree_proc(self.h_tree, TREE_ITEM_SELECT, id_item=target_id)


    def hide(self):
        dlg_proc(self.h, DLG_HIDE)


    def tree_on_click(self, id_dlg, id_ctl, data='', info=''):
        _lmb_pressed = 'L' in app_proc(PROC_GET_KEYSTATE, '')
        if _lmb_pressed  and  self._activate_item():
            self.hide()

    def tree_on_click_dbl(self, id_dlg, id_ctl, data='', info=''):
        if self._activate_item():
            self.hide()


    def _on_key(self, id_dlg, id_ctl, data='', info=''):
        key_code = id_ctl
        state = data

        if key_code in {VK_ENTER, VK_SPACE}  and  not state:
            if self._activate_item():
                self.hide()
            return False

        elif key_code == VK_ESCAPE  and  not state:
            self.hide()
            return False


    def on_deact(self, id_dlg, id_ctl, data='', info=''):
        if self.is_busy:
            return

        timer_proc(TIMER_START_ONE, 'module=cuda_breadcrumbs;func=hide_tree;', 100)

    def on_hide(self, id_dlg, id_ctl, data='', info=''):
        if self._on_hide:
            self._on_hide()
            self._on_hide = None


    def _activate_item(self, id_item=None):
        """ opens tree item (file, directory)
            returns True if ok to close
        """

        if id_item is None:
            id_item = tree_proc(self.h_tree, TREE_ITEM_GET_SELECTED)
            if id_item is None:
                return

        edt = Editor(self.h_ed)
        if self._mode == self.MODE_FILE:
            sel_item = self.id_map[id_item]
            if not sel_item.is_dir:     # open file
                path = sel_item.full_path
                if path != edt.get_filename():
                    file_open(path)
                    return True
            else:           # load directory
                if not sel_item.children: # not checked yet
                    sel_item.children = load_dir(sel_item.full_path, parent=sel_item)
                    self._fill_tree(sel_item.children,  parent=sel_item.id)
                    if sel_item.children:
                        tree_proc(self.h_tree, TREE_ITEM_UNFOLD, id_item=sel_item.id)

        elif self._mode == self.MODE_CODE:
            x0,y0, x1,y1 = tree_proc(self.h_tree, TREE_ITEM_GET_RANGE, id_item=id_item)
            if x0 != -1  and  y0 != -1:     # move caret to target range
                _top = max(0, y0-3)
                edt.set_prop(PROP_LINE_TOP, _top)
                edt.set_caret(x0,y0, options=CARET_OPTION_UNFOLD)


    @lock_tree
    def _fill_tree(self, children, parent=0):
        """ fills tree with children: list[Node]
            parent - id_item in tree to parent new nodes
        """
        if parent == 0: # clear tree and data
            tree_proc(self.h_tree, TREE_ITEM_DELETE, id_item=0)
            self.id_map.clear()

        for ch in children:
            if not SHOW_HIDDEN_FILES  and  ch.is_hidden:
                continue

            if ch.is_dir:
                im_ind = FileIcons.get_dir_ic_ind(default=-1)
            else:
                im_ind = FileIcons.get_ic_ind(ch.name, default=-1)

            id_ = tree_proc(self.h_tree, TREE_ITEM_ADD, id_item=parent, index=-1, text=ch.name,
                            image_index=im_ind)
            self.id_map[id_] = ch
            ch.id = id_
            if ch.children:
                self._fill_tree(ch.children, parent=id_)


    def _setup_tree(self, h_ed, on_hide, btn_rect):
        self.h_ed = h_ed
        self._on_hide = on_hide

        if self.h is None:
            self.h = self.init_form()
        self._update_colors()
        self._update_icons()

        tree_proc(self.h_tree, TREE_ITEM_DELETE, id_item=0)

        # set dlg position
        dlg_x,dlg_y, dlg_h = _get_dlg_pos(btn_rect, self._mode)
        dlg_proc(self.h, DLG_PROP_SET, prop={
            'h': dlg_h,
            'x': dlg_x,
            'y': dlg_y,
        })

    def _update_colors(self):
        _colors = app_proc(PROC_THEME_UI_DICT_GET, '')
        _color_form_bg = _colors['TabBg']['color']
        dlg_proc(self.h, DLG_PROP_SET, prop={ 'color': _color_form_bg })

    def _update_icons(self):
        h_im = None
        if self._mode == self.MODE_FILE:    h_im = self.h_im_file
        elif self._mode == self.MODE_CODE:  h_im = self.h_im_code

        if h_im is not None:
            tree_proc(self.h_tree, TREE_SET_IMAGELIST, text=h_im)


    def _get_tree_id(self, path_items, ind=0, id_=0):
        # recursion because nodes can have same names (html...)
        name = path_items[ind]
        items = tree_proc(self.h_tree, TREE_ITEM_ENUM, id_item=id_) # list[id,name] or None
        if not items:
            return None

        match_ids = (id_ for id_,item_name in items  if item_name == name)
        for id_item in match_ids:
            if ind == len(path_items)-1: # found last
                return id_item
            else:
                res = self._get_tree_id(path_items, ind+1, id_=id_item)
                if res is not None:
                    return res


def load_filepath_tree(fn, root):
    """ loads Node-tree from filesystem - from `root` to `fn`s directory
    """
    rel_path = fn.relative_to(root)

    data = FileNode(root.as_posix(), is_dir=True, is_hidden=False, parent=None, children=[])
    path = root
    item = data
    path_parts = list(rel_path.parts)
    while True:
        item.children.extend(load_dir(path, parent=item))

        if not path_parts:
            break

        name = path_parts.pop(0)
        path = os.path.join(path, name)
        if os.path.isfile(path):
            break
        item = next((it for it in item.children  if it.name == name), None)
        if item is None:
            print('NOTE: Breadcrumbs - can\'t find file: {}'.format(path))
            break

    # make sure all main-path items are visible
    if not SHOW_HIDDEN_FILES:
        item = data
        for name in rel_path.parts:
            item = next((ch for ch in item.children  if ch.name == name), None)
            if item is None:
                break
            item.is_hidden = False

    return data

def load_dir(path, parent=None):
    """ loads `FileNode`s from a single directory: `path`
        parent - parent `FileNode` for loaded children
    """
    items = []
    try:
        for entry in os.scandir(path):
            children = [] if entry.is_dir() else ()
            if IS_WIN:
                is_hidden = bool(entry.stat().st_file_attributes & FILE_ATTRIBUTE_HIDDEN)
            else:
                is_hidden = entry.name.startswith('.')
            node = FileNode(entry.name,  entry.is_dir(), is_hidden,  parent=parent,  children=children)
            items.append( node )
    except PermissionError:
        print('PermissionError: can\'t open: {}'.format(path))
    except os.error:
        pass

    # sort, name or extension
    if SORT_TYPE == 'ext':
        sort_key = lambda d: (not d.is_dir, d.ext, d.name.lower())
    else: # name -- default
        sort_key = lambda d: (not d.is_dir, d.name.lower())

    items.sort(key=sort_key, reverse=SORT_REVERSE)
    return items


def get_data_item(path_names, data):
    """ gets a single `Node` from `Node` tree by path: `path_names` (example: ['/', 'etc', 'cfg.cfg'])
    """
    for name in path_names:
        data = next(filter(lambda x: x.name==name,  data.children), None)
        if data is None:
            return None
    return data


def _get_dlg_pos(btn_rect, mode):
    screen_rect = app_proc(PROC_COORD_MONITOR, '')

    dlg_h = DLG_H
    if mode == TreeDlg.MODE_CODE  and  CODE_TREE_H is not None:
        if CODE_TREE_H == -1: # fullscreen
            dlg_h = screen_rect[3]
        #elif CODE_TREE_H == 0: -- no change
        elif CODE_TREE_H > 0: # pixel height
            dlg_h = CODE_TREE_H

    x,y, w,h = btn_rect
    dlg_x = x
    if POSITION_BOTTOM:
        dlg_y = y-dlg_h
        if dlg_y < 0: # if dialog doesnt fit on top - show it to the right of clicked button
            dlg_y = 0
            dlg_x = x+w
    else: # position top
        dlg_y = y+h
        if dlg_y+dlg_h > screen_rect[3]: # if dialog doesnt fit on bottom - show it to side of btn
            dlg_y = screen_rect[3] - dlg_h
            dlg_x = x+w

    if dlg_x+DLG_W > screen_rect[2]: # if doesnt fit on right - clamp to screen
        dlg_x = screen_rect[2]-DLG_W

    return dlg_x,dlg_y, dlg_h


class Node:
    __slots__ = ['name', 'is_dir', 'parent', 'children', 'id']

    #def __init__(self, name, is_dir, is_hidden, parent, children=(), id_=None):
    def __init__(self, name, is_dir, parent, children=(), id_=None):
        self.name = name
        self.is_dir = is_dir
        self.parent = parent
        self.children = children
        self.id = id_

    @property
    def path_items(self):
        names = []
        item = self
        while item:
            names.append(item.name)
            item = item.parent

        names.reverse()
        return names


class FileNode(Node):
    __slots__ = ['ext', 'is_hidden', ]

    def __init__(self, name, is_dir, is_hidden, parent, children=(), id_=None):
        super(FileNode, self).__init__(name, is_dir, parent, children, id_)
        self.ext = os.path.splitext(name)[1].lower()  if not is_dir else  ''
        self.is_hidden = is_hidden

    @property
    def full_path(self):
        return os.path.join(*self.path_items)

    def __str__(self):
        return f'{self.name} [{"d" if self.is_dir else "f"}:{self.id}] children={len(self.children)}'

    def as_dict(self):
        return {
            'name': self.name,
            'is_dir': self.is_dir,
            #'parent': '...',
            'children': [ch.as_dict() for ch in self.children],
            'id': self.id,
        }


class FileIcons:

    _h_im = None
    _ic_map = {}

    _fn_ic = os.path.join(app_path(APP_DIR_DATA), 'filetypeicons', 'vscode_16x16')
    _fn_ic_j = os.path.join(_fn_ic, 'icons.json')
    try:
        with open(_fn_ic_j, 'r') as f:
            LEX_MAP = json.load(f)
    except:
        LEX_MAP = {}

    @classmethod
    def init(cls, h_im):
        cls._h_im = h_im
        cls._ic_map.clear() # jic

    @classmethod
    def get_ic_ind(cls, fn, default=None):
        lex = lexer_proc(LEXER_DETECT, fn)
        if lex is None:
            return default

        if isinstance(lex, str):
            ind = cls._get_lex_ic_ind(lex)
            return ind  if ind is not None else  default
        else: # tuple
            gen = (cls._get_lex_ic_ind(l) for l in lex) # lexers' icon indexes or None's
            return next(filter(None, gen),  default) # first non-`None` value


    @classmethod
    def get_dir_ic_ind(cls, default=None):
        ind = cls._get_lex_ic_ind('_dir') # _dir is from `_fn_ic_j`
        return ind  if ind is not None else  default

    #TODO handle same file for different lexers
    @classmethod
    def _get_lex_ic_ind(cls, lex):
        if lex in cls._ic_map:
            return cls._ic_map[lex]

        if lex in cls.LEX_MAP:
            path = os.path.join(cls._fn_ic, cls.LEX_MAP[lex])
            ind = imagelist_proc(cls._h_im, IMAGELIST_ADD, path)
            cls._ic_map[lex] = ind

            return ind







