const ProxyChain = require('proxy-chain');

const server = new ProxyChain.Server({
    port: 8000,
    verbose: true,
    prepareRequestFunction: ({ request }) => {
        return {
            upstreamProxyUrl: 'http://firecloudvn:firecloudvn@4gusa2.firecloud.vn:8667',
        };
    },
});

server.listen(() => {
    console.log(`➡️ Proxy server đang chạy tại http://127.0.0.1:8000`);
});
