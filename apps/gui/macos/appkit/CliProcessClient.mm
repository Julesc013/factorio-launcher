// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "CliProcessClient.h"
#import "CommandClient.h"

static const NSTimeInterval FacManCliTimeoutSeconds = 30.0;
static const NSUInteger FacManMaximumStdoutBytes = 16U * 1024U * 1024U;
static const NSUInteger FacManMaximumStderrBytes = 64U * 1024U;

static NSString *FacManPipeText(NSData *data);
static NSData *FacManReadBounded(NSFileHandle *handle, NSUInteger maximumBytes, BOOL *exceeded);
static FacManCommandResult *FacManDecodeResult(
    FacManCommandDefinition *command,
    NSInteger exitCode,
    NSString *stdoutText,
    NSString *stderrText);

@interface FacManCliProcessClient ()
@property(nonatomic, strong) NSTask *activeTask;
@property(nonatomic, strong) NSMutableSet<NSTask *> *cancelledTasks;
@end

@implementation FacManCliProcessClient

- (instancetype)init
{
    self = [super init];
    if (self) _cancelledTasks = [NSMutableSet set];
    return self;
}

- (void)cancelCurrentCommand
{
    NSTask *task = nil;
    @synchronized(self) {
        task = self.activeTask;
        if (task != nil) [self.cancelledTasks addObject:task];
    }
    if ([task isRunning]) [task terminate];
}

- (void)invokeCommand:(FacManCommandDefinition *)command
              payload:(NSDictionary<NSString *, id> *)payload
            workspace:(NSString *)workspace
              cliPath:(NSString *)cliPath
           completion:(FacManCliProcessCompletion)completion
{
    [self cancelCurrentCommand];
    NSString *executable = [self resolveExecutable:cliPath];
    if ([executable length] == 0) {
        completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                   backendId:command.backendId
                                                refusalCode:@"frontend_backend_unavailable"
                                              refusalReason:@"No facman CLI executable is configured, bundled with the AppKit app, or available through FACMAN_CLI."]);
        return;
    }

    NSString *trimmedWorkspace = [workspace stringByTrimmingCharactersInSet:
        [NSCharacterSet whitespaceAndNewlineCharacterSet]];

    @try {
        NSTask *task = [[NSTask alloc] init];
        [task setLaunchPath:executable];
        [task setArguments:@[ @"rpc", @"--stdio" ]];
        NSPipe *stdinPipe = [NSPipe pipe];
        NSPipe *stdoutPipe = [NSPipe pipe];
        NSPipe *stderrPipe = [NSPipe pipe];
        [task setStandardInput:stdinPipe];
        [task setStandardOutput:stdoutPipe];
        [task setStandardError:stderrPipe];

        dispatch_group_t group = dispatch_group_create();
        __block NSData *stdoutData = nil;
        __block NSData *stderrData = nil;
        __block BOOL stdoutExceeded = NO;
        __block BOOL stderrExceeded = NO;
        __block BOOL timedOut = NO;
        dispatch_group_async(group, dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
            stdoutData = FacManReadBounded(
                [stdoutPipe fileHandleForReading], FacManMaximumStdoutBytes, &stdoutExceeded);
        });
        dispatch_group_async(group, dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
            stderrData = FacManReadBounded(
                [stderrPipe fileHandleForReading], FacManMaximumStderrBytes, &stderrExceeded);
        });
        dispatch_group_enter(group);
        [task setTerminationHandler:^(NSTask *finishedTask) {
            (void)finishedTask;
            dispatch_group_leave(group);
        }];
        [task launch];
        @synchronized(self) { self.activeTask = task; }
        NSDictionary *request = @{
            @"schema": @"facman.transport_request.v1",
            @"protocol_version": @1,
            @"request_id": [[NSUUID UUID] UUIDString],
            @"workspace": trimmedWorkspace ?: @"",
            @"command": command.backendId,
            @"dry_run": @(command.dryRunDefault),
            @"payload": payload ?: @{}
        };
        NSData *requestData = [NSJSONSerialization dataWithJSONObject:request options:0 error:nil];
        [[stdinPipe fileHandleForWriting] writeData:requestData];
        [[stdinPipe fileHandleForWriting] closeFile];

        dispatch_after(
            dispatch_time(DISPATCH_TIME_NOW, (int64_t)(FacManCliTimeoutSeconds * NSEC_PER_SEC)),
            dispatch_get_global_queue(QOS_CLASS_UTILITY, 0),
            ^{
                if ([task isRunning]) {
                    timedOut = YES;
                    [task terminate];
                }
            });

        dispatch_group_notify(group, dispatch_get_main_queue(), ^{
            BOOL cancelled = NO;
            @synchronized(self) {
                cancelled = [self.cancelledTasks containsObject:task];
                [self.cancelledTasks removeObject:task];
                if (self.activeTask == task) self.activeTask = nil;
            }
            if (cancelled) {
                completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                           backendId:command.backendId
                                                        refusalCode:@"frontend_backend_cancelled"
                                                      refusalReason:@"The backend command was cancelled."]);
                return;
            }
            if (timedOut) {
                completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                           backendId:command.backendId
                                                        refusalCode:@"frontend_backend_timeout"
                                                      refusalReason:@"The backend command exceeded the AppKit command timeout and was terminated."]);
                return;
            }
            if (stdoutExceeded || stderrExceeded) {
                completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                           backendId:command.backendId
                                                        refusalCode:@"frontend_backend_output_too_large"
                                                      refusalReason:@"The backend process exceeded its bounded output budget."]);
                return;
            }
            completion(FacManDecodeResult(
                command,
                [task terminationStatus],
                FacManPipeText(stdoutData),
                FacManPipeText(stderrData)));
        });
    } @catch (NSException *exception) {
        completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                   backendId:command.backendId
                                                refusalCode:@"frontend_backend_error"
                                              refusalReason:[exception reason] ?: @"AppKit command transport failed."]);
    }
}

- (NSString *)resolveExecutable:(NSString *)configuredPath
{
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSString *trimmedPath = [configuredPath stringByTrimmingCharactersInSet:
        [NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([trimmedPath length] > 0 && [fileManager isExecutableFileAtPath:trimmedPath]) return trimmedPath;
    NSString *envPath = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_CLI"];
    envPath = [envPath stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([envPath length] > 0 && [fileManager isExecutableFileAtPath:envPath]) return envPath;
    NSString *bundledPath = [[NSBundle mainBundle] pathForResource:@"facman" ofType:nil];
    if ([bundledPath length] > 0 && [fileManager isExecutableFileAtPath:bundledPath]) return bundledPath;
    return @"facman";
}

@end

static NSString *FacManPipeText(NSData *data)
{
    NSString *text = [[NSString alloc] initWithData:data ?: [NSData data] encoding:NSUTF8StringEncoding];
    return text ?: @"";
}

static NSData *FacManReadBounded(NSFileHandle *handle, NSUInteger maximumBytes, BOOL *exceeded)
{
    NSMutableData *output = [NSMutableData data];
    for (;;) {
        NSData *chunk = [handle availableData];
        if ([chunk length] == 0) break;
        const NSUInteger remaining = maximumBytes > [output length] ? maximumBytes - [output length] : 0;
        if ([chunk length] > remaining) {
            if (remaining > 0) [output appendData:[chunk subdataWithRange:NSMakeRange(0, remaining)]];
            if (exceeded != NULL) *exceeded = YES;
        } else {
            [output appendData:chunk];
        }
    }
    return output;
}

static NSString *FacManDictionaryText(NSDictionary *dictionary, NSString *key)
{
    id value = [dictionary objectForKey:key];
    return [value isKindOfClass:[NSString class]] ? value : @"";
}

static FacManCommandResult *FacManDecodeResult(
    FacManCommandDefinition *command,
    NSInteger exitCode,
    NSString *stdoutText,
    NSString *stderrText)
{
    NSData *data = [stdoutText dataUsingEncoding:NSUTF8StringEncoding];
    NSDictionary *document = data == nil ? nil : [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    NSDictionary *error = [[document objectForKey:@"error"] isKindOfClass:[NSDictionary class]]
        ? [document objectForKey:@"error"] : nil;
    BOOL refused = exitCode != 0 || ![[document objectForKey:@"outcome"] isEqual:@"ok"] || error != nil;
    return [[FacManCommandResult alloc] initWithCommandId:command.commandId
                                                backendId:command.backendId
                                                 exitCode:exitCode
                                               stdoutText:stdoutText
                                               stderrText:stderrText
                                                  refused:refused
                                               refusalCode:FacManDictionaryText(error, @"code")
                                             refusalReason:FacManDictionaryText(error, @"message")
                                                   outcome:FacManDictionaryText(document, @"outcome")];
}
