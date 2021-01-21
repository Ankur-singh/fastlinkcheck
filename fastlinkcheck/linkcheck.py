# AUTOGENERATED! DO NOT EDIT! File to edit: linkcheck.ipynb (unless otherwise specified).

__all__ = ['get_links', 'local_urls', 'html_exists', 'broken_local', 'broken_urls', 'link_check']

# Cell
from fastcore.all import *
from html.parser import HTMLParser
from urllib.parse import urlparse,urlunparse
from fastcore.script import SCRIPT_INFO
import sys
import socket
from http.client import InvalidURL
from urllib.error import HTTPError,URLError

# Cell
class _HTMLParseAttrs(HTMLParser):
    def reset(self):
        super().reset()
        self.found = set()
    def handle_starttag(self, tag, attrs):
        a = first(v for k,v in attrs if k in ("src","href"))
        if a: self.found.add(a)
    handle_startendtag = handle_starttag

# Cell
def get_links(fn):
    "List of all links in file `fn`"
    h = _HTMLParseAttrs()
    h.feed(Path(fn).read_text())
    return L(h.found)

# Cell
def _local_url(u, root, host, fname):
    "Change url `u` to local path if it is a local link"
    fpath = Path(fname).parent
    islocal=False
    # remove `host` prefix
    for o in 'http://','https://','http://www.','https://www.':
        if host and u.startswith(o+host): u,islocal = remove_prefix(u, o+host),True
    # remove params, querystring, and fragment
    p = list(urlparse(u))[:5]+['']
    # local prefix, or no protocol or host
    if islocal or (not p[0] and not p[1]):
        u = p[2]
        if u and u[0]=='/': return (root/u[1:]).resolve()
        else: return (fpath/u).resolve()
    # URLs without a protocol are "protocol relative"
    if not p[0]: p[0]='http'
    # mailto etc are not checked
    if p[0] not in ('http','https'): return ''
    return urlunparse(p)

# Cell
class _LinkMap(dict):
    """A dict that pretty prints Links and their associated locations."""
    def _repr_locs(self, k): return '\n'.join(f'  - `{p}`' for p in self[k])
    def __repr__(self):
        rstr = L(f'\n- {k!r} was found in the following pages:\n{self._repr_locs(k)}' for k in self).concat()
        return '\n'.join(rstr)
    _repr_markdown_ = __repr__

# Cell
def local_urls(path:Path, host:str):
    "returns a `dict` mapping all HTML files in `path` to a list of locally-resolved links in that file"
    path=Path(path)
    fns = L(path.glob('**/*.html'))+L(path.glob('**/*.htm'))
    found = [(fn.resolve(),_local_url(link, root=path, host=host, fname=fn))
             for fn in fns for link in get_links(fn)]
    return _LinkMap(groupby(found, 1, 0))

# Cell
def html_exists(o):
    "If a path without a suffix is proivded, see if the same path with a .html suffix exists"
    return (o.parent / (o.name + '.html') if not o.suffix else o).exists() or o.exists()

# Cell
def broken_local(links, ignore_paths=None):
    "List of items in keys of `links` that are `Path`s that do not exist"
    ignore_paths = setify(ignore_paths)
    return L(o for o in links if isinstance(o,Path) and o not in ignore_paths and not html_exists(o))

def urlcheck_(url, timeout=200):
    if not url: return True
    try:
        u = urlopen(url)
        return u.status<400
    except URLError: return False
    except socket.timeout: return False
    except InvalidURL: return False

# Cell
def broken_urls(links, ignore_urls=None):
    "List of items in keys of `links` that are URLs that return a failure status code"
    ignore_urls = setify(ignore_urls)
    its = L(o for o in links if isinstance(o, str) and o not in ignore_urls)
    working_urls = parallel(urlcheck_, its, n_workers=32, threadpool=True)
    return L(o for o,p in zip(its,working_urls) if not p)

# Cell
@call_parse
def link_check(path:Param("Root directory searched recursively for HTML files", str),
               host:Param("Host and path (without protocol) of web server", str)=None,
               config_file:Param("Location of file with urls to ignore",str)=None):
    "Check for broken links recursively in `path`."
    path = Path(path)
    assert path.exists(), f"{path.absolute()} does not exist."
    is_cli = (SCRIPT_INFO.func == 'link_check')
    if config_file: assert Path(config_file).is_file(), f"{config_file} is either not a file or doesn't exist."
    ignore = L(x.strip() for x in (Path(config_file).readlines() if config_file else ''))
    links = local_urls(path, host=host)
    ignore_paths = set((path/o).resolve() for o in ignore if not urlvalid(o))
    ignore_urls = set(ignore.filter(urlvalid))
    lm = _LinkMap({k:links[k] for k in (broken_urls(links, ignore_urls) + broken_local(links, ignore_paths))})
    if is_cli and lm:
        sys.stderr.write(f'\nERROR: The Following Broken Links or Paths were found:\n{lm}')
        sys.exit(1)
    if is_cli and not lm: print('No broken links found!')
    return lm
