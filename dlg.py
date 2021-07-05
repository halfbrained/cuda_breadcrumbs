import os
import json
from pathlib import Path

from cudatext import *

"""
#TODOs
* search
"""

VK_ENTER = 13
VK_ESCAPE = 27
VK_SPACE = 0x20

DLG_W = 250
DLG_H = 400


SORT_TYPE = 'name'
SORT_REVERSE = False


class TreeDlg:
    MODE_NONE = 10
    MODE_FILE = 11
    MODE_CODE = 12

    def __init__(self, opts=None):
        global SORT_TYPE

        self.h = None
        self.data = None
        self.id_map = {} # tree id -> `Node`

        self._mode = self.MODE_NONE

        self._tree_busy = False

        if opts:
            SORT_TYPE = opts.get('sort_type', SORT_TYPE)


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
                'on_deact': lambda *args,**vargs: self.hide(),
                })

        # tree ##########################
        n = dlg_proc(h, DLG_CTL_ADD, 'treeview')
        dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': 'tree',
                'align': ALIGN_CLIENT,
                'on_change': self.tree_on_click,
                #'on_click_dbl': self.tree_on_click_dbl,
                })
        self.h_tree = dlg_proc(h, DLG_CTL_HANDLE, index=n)
        tree_proc(self.h_tree, TREE_THEME)

        # init icons
        h_im = tree_proc(self.h_tree, TREE_GET_IMAGELIST)
        FileIcons.init(h_im)

        return h


    def show_dir(self, fn, root, btn_rect):
        """ btn_rect - screen (x,y, w,h) rect of button where tree should be shown
        """
        fn, root = Path(fn), Path(root)
        self._mode = self.MODE_FILE

        if self.h is None:
            self.h = self.init_form()

        self.data = load_filepath_tree(fn, root)

        self._fill_tree( self.data.children )

        # select `fn` tree item
        _rel_path = fn.relative_to(root)
        sel_item = get_data_item(_rel_path.parts,  self.data)
        if sel_item  and  sel_item.parent:
            tree_proc(self.h_tree, TREE_ITEM_SELECT, id_item=sel_item.id)

        # set dlg position
        x,y, w,h = btn_rect
        dlg_proc(self.h, DLG_PROP_SET, prop={
            'x': x+w,
            'y': y+h-DLG_H,
        })

        dlg_proc(self.h, DLG_SHOW_MODAL)


    def show_data(self, data, selected, btn_rect):
        #self._mode = self.MODE_CODE
        pass

    def hide(self):
        dlg_proc(self.h, DLG_HIDE)


    def tree_on_click(self, id_dlg, id_ctl, data='', info=''):
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


    def _activate_item(self, id_item=None):
        """ opens tree item (file, directory)
            returns True if ok to close
        """
        if self._mode != self.MODE_FILE:
            return

        if id_item is None:
            id_item = tree_proc(self.h_tree, TREE_ITEM_GET_SELECTED)
            if id_item is None:
                return

        sel_item = self.id_map[id_item]
        if not sel_item.is_dir:     # open file
            path = sel_item.full_path
            if path != ed.get_filename():
                file_open(path)
                return True

        else:   # load directory
            if not sel_item.children: # not checked yet
                sel_item.children = load_dir(sel_item.full_path, parent=sel_item)
                self._fill_tree(sel_item.children,  parent=sel_item.id)
                if sel_item.children:
                    tree_proc(self.h_tree, TREE_ITEM_UNFOLD, id_item=sel_item.id)


    def _fill_tree(self, children, parent=0):
        """ fills tree with children: list[Node]
            parent - id_item in tree to parent new nodes
        """
        if parent == 0: # clear tree and data
            tree_proc(self.h_tree, TREE_ITEM_DELETE, id_item=0)
            self.id_map.clear()

        for ch in children:
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


def load_filepath_tree(fn, root):
    """ loads Node-tree from filesystem - from `root` to `fn`s directory
    """
    rel_path = fn.relative_to(root)

    data = Node(root.as_posix(), True, parent=None, children=[])
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
        item = next(it for it in item.children  if it.name == name)
    return data

def load_dir(path, parent=None):
    """ loads `Node`s from a single directory: `path`
        parent - parent `Node` for loaded children
    """
    items = []
    for entry in os.scandir(path):
        children = [] if entry.is_dir() else ()
        items.append( Node(entry.name,  entry.is_dir(),  parent=parent,  children=children) )

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


class Node:
    __slots__ = ['name', 'ext', 'is_dir', 'parent', 'children', 'id']

    def __init__(self, name, is_dir, parent, children=(), id_=None):
        self.name = name
        self.ext = os.path.splitext(name)[1].lower()  if not is_dir else  ''
        self.is_dir = is_dir
        self.parent = parent
        self.children = children
        self.id = id_

    @property
    def full_path(self):
        names = []
        item = self
        while item:
            names.append(item.name)
            item = item.parent

        return os.path.join(*reversed(names))

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







