# Owner-shell FD byte probe02: limited target observation

Статус: **confirmed-on-target limited observation; independent saved-evidence
replay PASS**. [Result JSON](result.json), [acquisition](acquire.py),
[scope/source contract](../../06-tools/android_fd_byte_microprobe/README.md).
Завершён 2026-11-08T23:29:56.914565 UTC. 13 events /395 accepted B;
probe stdout54 B, wrapper rc0, outer stderr0. Host-measured probe elapsed
0.769395562 s; guarded whole run9.028409 s, не device timing bound.

Отдельный новый template обращается к /proc/$$/fd/8, то есть FD владельца shell.
После unlink exact LF1 B и LF+NUL2 B сохранены в данном invocation. Command
substitution потеряла trailing LF и NUL; captured substitution stderr0 B.
Эти данные не разрешают переносить binary diagnostics через substitution.
Own directory independently absent, same boot, mutex absent, Enforcing.
Fresh nonce отличается от01; source/render/order/private events/streams/caps
независимо проверены, без публикации private values.

## Frozen sources и host checks

- probe_owner_fd.sh.in SHA256: 86e01f66afee1c7849813ed5968e9698c5267c9f17597c34094fa60b445068a2.
- probe_owner_fd.py SHA256: dca1de834ab53e900c03412761f31e82ad9c9082b973943969e86aa1c8270296.
- acquire.py SHA256: 7946d4a8162cfbe551e3399c8862bfdf0d624c57b1f7a419329777dce6d0d01d.

Independent host suite7 tests normal/-O, с реальными dash/bash cases, PASS;
acquisition8 fake-socket tests normal/-O PASS. Source/result bytes не менялись.
Host deadline остаётся acceptance boundary, не remote cancellation.
Preflight/binding flags поддержаны source + lead record, не отдельным raw host
preflight transcript. Incomplete current transport-frame bytes не сохраняются.

## Не доказано

Это лишь одна owner-shell FD byte observation и успешная own cleanup,
не all-failure cleanup, full wrapper compatibility, batch admission, root↔shell
lifecycle, clock/suspend/kill-grace guarantee или PWM proof. [Probe01](../android_fd_byte_microprobe_20261108_01/result.md)
failed external cat /proc/self/fd/8; старый validate_capture.sh использует этот
путь только builtin -f/-s checks. Ни причина CLOEXEC, ни необходимость patch
старого wrapper не установлены.

13 qualified runtime blobs unchanged. Нет DSI/settings/trace/reboot; camera
только identity. Brightness/current restore не измерены. Последний experimental
DSI остаётся timedstock03 19:07:07.888880 UTC, native828 restored тогда.
Unknown14 disabled;37/45/8/60/overall600 сохранены; PWM>=2000 Hz не доказаны.
Следующий milestone: небольшой fixed non-DSI synthetic acquisition/receipt
root↔shell probe ещё строится offline; не generic57 batch.
