
import time
import subprocess
from pathlib import Path
from loguru import logger
from typing import List, Union, Optional, Dict

from playwright.sync_api import sync_playwright, Page, Route, ProxySettings
from playwright_stealth import stealth_sync
from pjstealth import stealth_sync


class BrowserType:
    chromium = 'chromium'
    firefox = 'firefox'
    webkit = 'webkit'
    
class Partial:
    def __init__(self, func, **kwargs):
        self.func = func
        self.kwargs = kwargs

    def __call__(self, *args):
        return self.func(*args, **self.kwargs)

class PlaywrightHandler:
    def __init__(self,
                executable_path: Union[str, Path] = None,
                headless:bool=None,
                args: List[str]=None,
                ignore_default_args: Union[bool, List[str]]=None,
                proxy: ProxySettings=None,
                browser_type: str=BrowserType.firefox, 
                **kwargs):
        """
        初始化浏览器
        1. 创建pw实例
        2. 创建browser对象

        Parameters
        ----------
        executable_path : Union[pathlib.Path, str, NoneType]
            Path to a browser executable to run instead of the bundled one. If `executablePath` is a relative path, then it is
            resolved relative to the current working directory. Note that Playwright only works with the bundled Chromium, Firefox
            or WebKit, use at your own risk.
        headless : Union[bool, NoneType]
            Whether to run browser in headless mode. More details for
            [Chromium](https://developers.google.com/web/updates/2017/04/headless-chrome) and
            [Firefox](https://developer.mozilla.org/en-US/docs/Mozilla/Firefox/Headless_mode). Defaults to `true` unless the
            `devtools` option is `true`.
        args : Union[List[str], NoneType]
            Additional arguments to pass to the browser instance. The list of Chromium flags can be found
            [here](http://peter.sh/experiments/chromium-command-line-switches/).
        ignore_default_args : Union[List[str], bool, NoneType]
            If `true`, Playwright does not pass its own configurations args and only uses the ones from `args`. If an array is
            given, then filters out the given default arguments. Dangerous option; use with care. Defaults to `false`.
        proxy : Union[{server: str, bypass: Union[str, NoneType], username: Union[str, NoneType], password: Union[str, NoneType]}, NoneType]
            Network proxy settings.
        browser_type : str
            可选： 'chromium', 'firefox', 'webkit'
        kwargs
            其他实例化参数
        """
        logger.info('start init playwright.')
        self.pw = sync_playwright().start()
        self.browser_type = self._get_browser_type(browser_type=browser_type)
        self.browser = self.browser_type.launch(
            executable_path=executable_path,
            headless=headless,
            args=args,
            ignore_default_args=ignore_default_args,
            proxy=proxy,
            **kwargs
        )
        self.context = None
        self.page = None
        self.save_stack = None
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        logger.info('start init playwright browser finish.')

    def _get_browser_type(self, browser_type: str=BrowserType.firefox):
        """
        获取browser类型
        """
        if browser_type == BrowserType.chromium:
            return self.pw.chromium
        elif browser_type == BrowserType.firefox:
            return self.pw.firefox
        elif browser_type == BrowserType.webkit:
            return self.pw.webkit
        else:
            # todo warning 没有匹配的类型，使用firefox
            logger.warning('browser_type not find. use firefox')
            return self.pw.firefox

    def _on_context_page(self, page: Page):
        """
        context 拦截器 在创建page对象后执行
        """
        stealth_sync(page)  # 浏览器伪造
        page.evaluate('''() =>{
                       Object.defineProperties(navigator,{
                         webdriver:{
                           get: () => false
                         }
                       })
                    }''')
        page.evaluate('''() => {
                      const originalQuery = window.navigator.permissions.query;
                      return window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                          Promise.resolve({ state: Notification.permission }) :
                          originalQuery(parameters)
                      );
                    }
                    ''')
        page.evaluate('''() =>{
                Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
                    });
                }''')
        
        self.on_page(page)

    def on_page(self, page: Page):
        """
        子类可以继承此方法，方便自定义创建page的动作
        """
        pass
    
    def _get_context(self,
                    user_agent: str = None,
                    extra_http_headers: Optional[Dict[str, str]] = None,
                    proxy: ProxySettings = None,
                    **kwargs
                    ):
        """
        获取上下文对象
        类似打开一个无痕浏览器

        Parameters
        ----------
        user_agent : Union[str, NoneType]
            Specific user agent to use in this context.
        extra_http_headers : Union[Dict[str, str], NoneType]
            An object containing additional HTTP headers to be sent with every request.
        proxy : Union[{server: str, bypass: Union[str, NoneType], username: Union[str, NoneType], password: Union[str, NoneType]}, NoneType]
            Network proxy settings to use with this context.

            > NOTE: For Chromium on Windows the browser needs to be launched with the global proxy for this option to work. If all
            contexts override the proxy, global proxy will be never used and can be any string, for example `launch({ proxy: {
            server: 'http://per-context' } })`.
        kwargs： 其他参数
        """
        if user_agent is None:
            user_agent = self.user_agent

        self.context = self.browser.new_context(
            user_agent=user_agent,
            extra_http_headers=extra_http_headers,
            proxy=proxy,
            ignore_https_errors=True,
            **kwargs
        )

        self.context.on('page', self._on_context_page)
        logger.info('create context finish.')

    def _clean_save_stack(self):
        self.save_stack = []
        logger.info('init save_stack.')

    def handle_route(self, route: Route, ignore_resource=None, save_stack=False):
        """
        ignore_resource  忽略资源的列表  ("image", "stylesheet", "media", "eventsource", "websocket")
        save_stack 是否保存堆栈
        """

        request = route.request
        if save_stack:
            self.save_stack.append(request)

        # 动态设置忽略的资源
        if ignore_resource is None:
            ignore_resource = []
        if request.resource_type in ignore_resource:
            route.abort()
        else:
            route.continue_()
    
    def get_new_page(self, 
                    user_agent: str = None,
                    extra_http_headers: Optional[Dict[str, str]] = None,
                    proxy: ProxySettings = None,

                    cookies: List[Dict[str, str]] = None,
                    headers: Dict[str, str] = None,
                    use_cache: bool=True,
                    save_stack: bool=False,
                    ignore_resource: List[str]=None,

                    **kwargs):
        """
        创建一个新的页面
        1. 根据参数以及self.context判断是否创建context对象。
        2. 设置request和response hook
        """
        if not self.context:
            self._get_context(
                user_agent=user_agent,
                extra_http_headers=extra_http_headers,
                proxy=proxy,
                **kwargs
            )
        
        if not self.context:
            raise Exception("实例化context失败")
        
        # todo 若多个页面，会影响到其他页面。
        if cookies:
            self.context.clear_cookies()
            self.context.add_cookies(cookies=cookies)
            logger.info('add cookies success.')

        page = self.context.new_page()

        if headers:
            page.set_extra_http_headers(headers=headers)
            logger.info('add headers success.')

        if not use_cache:
            page.set_extra_http_headers({"Cache-Control": "no-cache"})
            logger.info('set Cache-Control use no-cache.')
        
        if ignore_resource and save_stack:
            self._clean_save_stack()
            page_global_hook = Partial(self.handle_route,
                                        ignore_resource=ignore_resource, 
                                        save_stack=save_stack)

            page.route("**/*", page_global_hook)
            logger.info('hook all request.')
        
        logger.info('page created.')

        return page
    
    def replace_iframe_element(self, page: Page):
        """
        replace iframe element outer_html
        """
        frames_lst = page.frames
        if len(frames_lst) < 2:
            return 

        for frame in frames_lst[1:]:
            content = frame.content()
            page.eval_on_selector(f'#{frame.name}', "(e, content) => e.outerHTML=content", content)
            # page.evaluate(f'(frame) => {{frame.outerHTML = `{content}`;}}', page.query_selector(f'#{frame.name}'))

    def goto_the_url(self, 
                    url: str,
                    user_agent: str=None,
                    cookies: Dict[str, str]=None,
                    headers: Dict[str, str]=None,
                    proxy: str=None,
                    use_cache: bool=True,
                    save_stack: bool=False,
                    ignore_resource: List[str]=None,
                    wait_for_selector: str=None,
                    exec_js: str=None,
                    exec_js_args: str=None,
                    timeout: int=30,
                    sleep: int=None,
                    page: Page=None,
                    **kwargs):
        """
        跳转到指定的url
        支持：
            1. 指定url
            2. 设置cookies  
            3. 设置headers  
            4. 执行指定js   
            5. 页面级代理  (上下文级代理, 类似于无痕浏览器） 
            6. 是否允许缓存  
            7. 等待元素  
            8. 请求堆栈  
            9. 忽略资源  
            10. iframe 标签替换

        """
        # todo 页面管理？
        if not self.page:
            self.page = page

        if not self.page:
            proxy_fm = None
            if proxy:
                proxy_fm = {'server': proxy}
                
            self.page: Page = self.get_new_page(
                user_agent=user_agent,
                proxy=proxy_fm,
                cookies=cookies,
                headers= headers,
                use_cache=use_cache,
                save_stack=save_stack,
                ignore_resource=ignore_resource,
                **kwargs
            )
            
        if not self.page:
            raise Exception("page create fail.")

        self.page.goto(url)

        if sleep:
            time.sleep(sleep)

        if wait_for_selector:
            self.page.wait_for_selector(wait_for_selector, timeout=timeout*1000)
        
        if exec_js:
            self.page.evaluate(exec_js, exec_js_args)

        self.replace_iframe_element(self.page)
        content = self.page.content()
        cookies = self.context.cookies()

        
        page_data = {
            "content": content,
            "cookies": cookies
        }
        if save_stack:
            page_data['stack'] = self.save_stack

        logger.info('page request finish.')

        return page_data
    
    def close_page(self, page: Page):
        try:
            page.close()
        except:
            logger.warning('page closed.')
            pass

    def close_context(self):
        try:
            self.context.close()
        except:
            logger.warning('context closed.')
            pass
    
    def close_browser(self):
        try:
            self.browser.close()
        except:
            logger.warning('browser closed.')
            pass

    def __del__(self):
        self.close_context()
        self.close_browser()


def playwright_test():
    pw = PlaywrightHandler()
    kwargs = {
        # 'url': 'http://myip.ipip.net',
        'url': 'http://sdbhgj.youzhicai.com/index/Notice.html?id=2ed513c0-bc27-45ed-8d82-a200d52f54f7&n=1',
        # 'url': 'http://zhaobiao.jsph.org.cn/supplier/release/cgInfoList?pageNo=4&pageSize=10',
        # 'save_stack': True,
        # 'proxy': 'socks5://spider-s0cks5User:pwd958j3Y42d2dssq@192.168.184.10:21101',
        # "wait_for_selector": '#detailUrl',
        # 'use_cache': False,
        # 'timeout': 5,
        'sleep': 3,
    }
    data = pw.goto_the_url(**kwargs)
    print(data['content'])


if __name__ == '__main__':
    playwright_test()
    




