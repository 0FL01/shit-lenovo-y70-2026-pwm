# Proc stat errno: source-only assessment

2026-11-09. Только сохранённые sanitized artifacts и официальный upstream source. Без новых host/proc/ADB/device checks, downloads, Git или runtime edits. Recovery admission отсутствует.

## Практический вывод

ESRCH от read уже открытого authenticated stat FD не является безусловным доказательством исчезновения task. Если доказано происхождение именно из proc_single_show, ошибка означает отсутствие PIDTYPE_PID association у удерживаемого struct pid в момент lookup. Syscall errno сам по себе происхождение не устанавливает. Сохранить cause-unproven/stopped; retry, skip процесса или восстановление adapter не следуют из результата.

## Host evidence и граница версии

- Local-retained historical evidence `host_runner_capability_check_attempt02_20261109.md` (not part of this publication): Linux x86_64, UID0, Python 3.13.5, Git 2.47.2; kernel release/build/config не указан.
- Local-retained historical evidence `host_prerequisite_refresh_20261109_01/RESULT.md` (not part of this publication): прежние process/executable/netns pins совпали; kernel release не указан.
- Local-retained historical evidence `host_linux_probe_bootstrap_20261109_01/BOOTSTRAP.md` (not part of this publication): одна proc mount record без найденного hidepid option; прочитанные PID namespace links совпали, netns self/PID1/ADB совпали. Universal visibility, ancestor coverage и отсутствие task-private FD tables не квалифицированы.
- [Exact historical owned-child sample](../owned_child_sample_20261109_01/RESULT.md): owned-child read успешен, failed-read attribution отсутствует; mount/PID namespace authentication не квалифицирована.

Version-appropriate host source из этих sanitized материалов выбрать невозможно. Далее v6.12 только прежний upstream reference, НЕ host equivalence и не телефонное ядро. Даже совпадение версии само по себе source equivalence не доказывает.

## Errno и permissions

[base.c:720–778](https://github.com/torvalds/linux/blob/v6.12/fs/proc/base.c#L720-L778): proc_single_show получает task через inode-held pid/PIDTYPE_PID и возвращает ESRCH при NULL. Hidepid path может вернуть ENOENT для существующего скрытого task. Но lookup/open и read уже открытого FD нельзя смешивать: read не выполняет новый numeric path lookup.

[array.c:442–644](https://github.com/torvalds/linux/blob/v6.12/fs/proc/array.c#L442-L644): do_task_stat возвращает 0. Ptrace access проверяется при генерации; denial обнуляет защищённые поля, не возвращает ESRCH. Успешная запись не удостоверяет доступ ко всем полям.

[read_write.c:422–544](https://github.com/torvalds/linux/blob/v6.12/fs/read_write.c#L422-L544) и [security.c:2653–2672](https://github.com/torvalds/linux/blob/v6.12/security/security.c#L2653-L2672): перед файловым read VFS вызывает security_file_permission и fsnotify permission path. Открытый FD не отменяет проверки; ошибка может прийти до proc callback.

[seccomp.c:1155–1165](https://github.com/torvalds/linux/blob/v6.12/kernel/seccomp.c#L1155-L1165): RET_ERRNO задаёт errno, пропуская syscall body. Даже ESRCH может быть синтетическим. Это source counterexample, не утверждение о host filter.

Другие прямые ошибки read path: EBADF/EINVAL/EFAULT; seq allocation: ENOMEM. Permission paths могут дать EACCES/EPERM; полный набор зависит от actual hooks/interposition. EIO/EINTR/ENOENT/неизвестные errno не означают исчезновение. Сохранять open/read/seek/close stages отдельно; close failure не заменяет read error.

## Buffer, EOF, retries

[seq_file.c:83–281](https://github.com/torvalds/linux/blob/v6.12/fs/seq_file.c#L83-L281), [single iterator:527–558](https://github.com/torvalds/linux/blob/v6.12/fs/seq_file.c#L527-L558): zero-count возвращает 0 без show. EOF после единственной записи не требует нового task lookup. Частичный read оставляет buffered bytes, выдаваемые после смерти task; bytes/EOF не являются свежим liveness proof. Overflow повторяет генерацию внутри kernel; position mismatch вызывает traverse с EAGAIN retry. Отрицательный show error сам не ретраится. Если уже скопированы bytes, seq возвращает их число вместо ошибки. Caller no-retry не гарантирует одну sampling attempt. Owned FD, отсутствие чужого seek/read и исходное состояние offset/buffer являются отдельными assumptions. Checked deadline не означает kernel cancellation guarantee.

## Zombie, threads, exec

[pid.c:384–442](https://github.com/torvalds/linux/blob/v6.12/kernel/pid.c#L384-L442), [exit.c:120–245](https://github.com/torvalds/linux/blob/v6.12/kernel/exit.c#L120-L245), [exit/reap:689–732](https://github.com/torvalds/linux/blob/v6.12/kernel/exit.c#L689-L732), [leader wait:1380–1390](https://github.com/torvalds/linux/blob/v6.12/kernel/exit.c#L1380-L1390): termination не равна отсутствию PID association. Zombie может читаться до release/reap; leader с живыми threads не reap-ится обычным wait. Полученный task reference позволяет show завершиться после concurrent detach. ESRCH из show не устанавливает точное время exit или уничтожение всех references. Исчезновение thread не равно смерти группы.

[exec.c:1094–1111](https://github.com/torvalds/linux/blob/v6.12/fs/exec.c#L1094-L1111): nonleader exec/de_thread наследует leader starttime и меняет PID associations. Held PID object НЕ immutable task_struct identity. Executable, credentials, FD ownership и thread identity требуют самостоятельной модели.

## RootPin: namespace symlink недостаточен

Source-backed inference, не host observation: [proc/self.c:10–25](https://github.com/torvalds/linux/blob/v6.12/fs/proc/self.c#L10-L25) формирует self по current TGID в namespace proc superblock. [namespaces.c:39–84](https://github.com/torvalds/linux/blob/v6.12/fs/proc/namespaces.c#L39-L84) получает namespace найденного task; [pid_namespace.c:312–323](https://github.com/torvalds/linux/blob/v6.12/kernel/pid_namespace.c#L312-L323) для ns/pid возвращает task_active_pid_ns(task).

Следовательно self/ns/pid может показывать active namespace caller даже при proc superblock в ancestor namespace. [Numeric proc lookup](https://github.com/torvalds/linux/blob/v6.12/fs/proc/base.c#L3318-L3326) использует namespace superblock. Напротив [pidfd_open](https://github.com/torvalds/linux/blob/v6.12/kernel/pid.c#L592-L609) вызывает find_get_pid/find_vpid; [find_vpid](https://github.com/torvalds/linux/blob/v6.12/kernel/pid.c#L299-L308) использует active namespace caller.

Future RootPin requirement: независимо доказать соответствие proc numeric namespace и pidfd_open numbering. Одно совпадение ns/pid symlink этого не доказывает. Новый qualification check здесь не предложен и не исполнен.

## Незакрытые assumptions

Actual kernel/config/patch provenance; доверенный read без errno injection; квалифицированные LSM/seccomp/notification paths; authenticated proc superblock/numbering linkage; owned неизменяемый FD/offset/buffer; точная PID/TID/TGID/exec модель. Даже их выполнение не доказывает непрерывную socket/accepted-FD custody или recovery route. STOCK15 HOLD, 14 disabled, production unchanged.
