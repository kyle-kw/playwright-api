# playwright-api

封装playwright无头浏览器，使用接口的形式进行调用。

项目特性

1. 使用多进程自动管理无头浏览器。
2. 使用gost进行sock5转发，可以使用验证的sock5代理。
3. 使用docker-compose进行部署，方便快速部署。


## 快速开始

```shell
docker build . -t playwright-api:1.0.0
docker compose up -d
```

TODO 待完善

- [ ] master线程监控子进程资源占用。
- [ ] gost sock5转发，抽离成独立服务。




