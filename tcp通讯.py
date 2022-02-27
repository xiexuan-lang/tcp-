import ctypes
import inspect
import re
import socket
import threading
from time import sleep


# 强制关闭线程的方法
def _async_raise(tid, exc_type):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exc_type):
        exc_type = type(exc_type)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exc_type))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


def get_host_ip() -> str:
    """
    获取本机IP地址
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


class TcpLogic:
    def __init__(self):
        self.tcp_socket = None
        self.sever_th = None
        self.client_th = None
        self.client_socket_list = list()
        self.link_flag = 0

    def tcp_server_start(self, port: int) -> None:
        """
        功能函数，TCP服务端开启的方法
        """
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 取消主动断开连接四次握手后的TIME_WAIT状态
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 设定套接字为非阻塞式
        self.tcp_socket.setblocking(False)
        self.tcp_socket.bind(("", port))
        self.tcp_socket.listen(5)  # 限制最大连接数
        self.sever_th = threading.Thread(target=self.tcp_server_concurrency)
        self.sever_th.start()
        print("TCP服务端正在监听端口:%s\n" % str(port))

    def tcp_server_concurrency(self) -> None:
        """
        功能函数，供创建线程的方法
        使用子线程用于监听并创建连接，使主线程可以继续运行，以免无响应
        使用非阻塞式并发用于接收客户端消息，减少系统资源浪费，使软件轻量化
        """
        while True:
            try:
                client_socket, client_address = self.tcp_socket.accept()
            except Exception as ret:
                sleep(0.002)
            else:
                client_socket.setblocking(False)
                # 将创建的客户端套接字存入列表,client_address为ip和端口的元组
                self.client_socket_list.append((client_socket, client_address))
                print(f"TCP服务端已连接IP:{client_address[0]} 端口:{client_address[1]}\n")
            # 轮询客户端套接字列表，接收数据
            for client, address in self.client_socket_list:
                try:
                    recv_info = client.recv(4096)
                except Exception as ret:
                    pass
                else:
                    if recv_info:
                        print(f"来自IP:{address[0]} 端口:{address[1]}:")
                        info = recv_info.decode("utf-8")  # 接收到的消息
                        print(info)

                    else:
                        client.close()
                        self.client_socket_list.remove((client, address))

    def tcp_client_start(self, ip: str, port: int) -> None:
        """
        功能函数，TCP客户端连接其他服务端的方法
        """
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = (ip, port)
        try:
            print("正在连接目标服务器……\n")
            self.tcp_socket.connect(address)
        except Exception as ret:
            print("无法连接目标服务器\n")
        else:
            self.client_th = threading.Thread(
                target=self.tcp_client_concurrency, args=(address,)
            )
            self.client_th.start()
            print("TCP客户端已连接IP:%s 端口:%s\n" % address)

    def tcp_client_concurrency(self, address) -> None:
        """
        功能函数，用于TCP客户端创建子线程的方法，阻塞式接收
        """
        while True:
            recv_info = self.tcp_socket.recv(4096)
            if recv_info:
                info = recv_info.decode("utf-8")
                print(f"来自IP:{address[0]} 端口:{address[1]}:")
                print(info)
            else:
                self.tcp_socket.close()
                print("从服务器断开连接\n")
                break

    def tcp_send(self, send_info: str) -> None:
        """
        功能函数，用于TCP服务端和TCP客户端发送消息
        """
        try:
            send_info_encoded = send_info.encode("utf-8")
            if self.link_flag == self.ServerTCP:
                # 向所有连接的客户端发送消息
                if self.client_socket_list:
                    for client, address in self.client_socket_list:
                        client.send(send_info_encoded)
                    print("TCP服务端已发送")
                    print(send_info)
            if self.link_flag == self.ClientTCP:
                self.tcp_socket.send(send_info_encoded)
                print("TCP客户端已发送")
                print(send_info)
        except Exception as ret:
            msg = "发送失败\n"
            print(msg)

    def tcp_close(self) -> None:
        """
        功能函数，关闭网络连接的方法
        """
        if self.link_flag == self.ServerTCP:
            for client, address in self.client_socket_list:
                client.shutdown(socket.SHUT_RDWR)
                client.close()
            self.client_socket_list = list()  # 把已连接的客户端列表重新置为空列表
            self.tcp_socket.close()
            print("已断开网络\n")

            try:
                stop_thread(self.sever_th)
            except Exception as ret:
                pass

        elif self.link_flag == self.ClientTCP:
            try:
                self.tcp_socket.shutdown(socket.SHUT_RDWR)
                self.tcp_socket.close()
                print("已断开网络\n")
            except Exception as ret:
                pass

            try:
                stop_thread(self.client_th)
            except Exception as ret:
                pass

    ServerTCP = 0
    ClientTCP = 1


Welcome = "欢迎使用网络调试助手-命令行版"


def port_check(port: int) -> bool:
    """
    检查用户输入的端口号是否合法
    """
    if -1 < port < 65536:
        return True
    else:
        return False


def input_port() -> int:
    """
    获取用户输入的端口号，如不合法则反复获取
    """
    while True:
        port = int(input("请输入端口号："))
        if port_check(port):
            break
        else:
            print("输入有误，请检查后再试")
    return port


def input_ip() -> str:
    """
    获取用户输入的IP地址，如不合法则反复获取
    """
    while True:
        ip = input("请输入IP地址：")
        if ip_check(ip):
            break
        else:
            print("输入有误，请检查后再试")
    return ip


def ip_check(ip: str) -> bool:
    """
    检查用户输入的IP地址是否合法
    """
    pattern = re.compile(
        r"(([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}([1-9]?\d|1\d\d|2[0-4]\d|25[0-5])"
    )
    return bool(re.fullmatch(pattern, ip))


def main():
    print(Welcome)
    print(f"本机IP地址为：{get_host_ip()}")
    t = TcpLogic()  # 实例化对象

    # 使用死循环以反复获得用户输入，直到用户输入合法
    while True:
        link_flag = int(input("请选择连接类型：\n0 -- 服务端\n1 -- 客户端\n"))
        if link_flag in (t.ServerTCP, t.ClientTCP):
            if link_flag == t.ServerTCP:
                t.link_flag = t.ServerTCP
                t.tcp_server_start(input_port())
            elif link_flag == t.ClientTCP:
                t.link_flag = t.ClientTCP
                t.tcp_client_start(input_ip(), input_port())
            break
        else:
            print("输入有误，请检查后再试")

    # 死循环获取用户在命令行的输入
    while True:
        user_input = input("输入要发送的信息：\n")
        if user_input == "exit":
            # 如果用户输入 exit ，则关闭退出
            t.tcp_close()
            break
        else:
            t.tcp_send(user_input)


if __name__ == "__main__":
    main()
