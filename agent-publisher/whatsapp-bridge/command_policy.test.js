'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { isAuthorizedChat, parsePublishCommand } = require('./command_policy');

test('publish requires a complete, explicit command and a single safe positive ID', () => {
    for (const command of ['/publish 81', ' /PUBLISH   81 ']) {
        assert.equal(parsePublishCommand(command), '81');
    }
    for (const command of [
        '81번 발행', '/발행 81', '/publisher 81', '/publish', '/publish 81 abc',
        '/publish 81 82', '/publish -1', '/publish 0', '/publish 81; echo test',
        '/publish 9007199254740992', 'publish 81',
    ]) {
        assert.equal(parsePublishCommand(command), null, command);
    }
});

test('own-account commands require a self-chat, not just fromMe', () => {
    const base = { ownJids: ['123:4@s.whatsapp.net', '456@lid'], ownerIds: [] };
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '123@s.whatsapp.net', fromMe: true }), true);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '456@lid', fromMe: true }), true);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '999@s.whatsapp.net', fromMe: true }), false);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '12345-10@g.us', fromMe: true }), false);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: 'status@broadcast', fromMe: true }), false);
});

test('incoming owner messages require explicit numeric allowlisting', () => {
    const base = { ownJids: ['123@s.whatsapp.net'], ownerIds: ['987', '654'] };
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '987@s.whatsapp.net', fromMe: false }), true);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '654@lid', fromMe: false }), true);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '999@s.whatsapp.net', fromMe: false }), false);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '987@g.us', fromMe: false }), false);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '987@s.whatsapp.net', fromMe: true }), false);
    assert.equal(isAuthorizedChat({ ...base, remoteJid: '987@s.whatsapp.net', fromMe: false, ownerIds: ['YOUR_OWNER_ID'] }), false);
});
