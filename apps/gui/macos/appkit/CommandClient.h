// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import <Foundation/Foundation.h>

typedef NS_ENUM(NSInteger, FacManCommandStatus) {
    FacManCommandStatusImplemented = 0,
    FacManCommandStatusStubbedWithRefusal = 1,
    FacManCommandStatusNotSupportedWithReason = 2
};

@interface FacManCommandDefinition : NSObject

@property(nonatomic, copy, readonly) NSString *commandId;
@property(nonatomic, copy, readonly) NSString *backendId;
@property(nonatomic, copy, readonly) NSString *screen;
@property(nonatomic, copy, readonly) NSString *label;
@property(nonatomic, copy, readonly) NSString *summary;
@property(nonatomic, copy, readonly) NSString *deferredReason;
@property(nonatomic, assign, readonly) FacManCommandStatus status;

- (instancetype)initWithCommandId:(NSString *)commandId
                        backendId:(NSString *)backendId
                           screen:(NSString *)screen
                            label:(NSString *)label
                          summary:(NSString *)summary
                   deferredReason:(NSString *)deferredReason
                            status:(FacManCommandStatus)status;

@end

@interface FacManCommandResult : NSObject

@property(nonatomic, copy, readonly) NSString *commandId;
@property(nonatomic, copy, readonly) NSString *backendId;
@property(nonatomic, assign, readonly) NSInteger exitCode;
@property(nonatomic, copy, readonly) NSString *stdoutText;
@property(nonatomic, copy, readonly) NSString *stderrText;
@property(nonatomic, assign, readonly) BOOL refused;
@property(nonatomic, copy, readonly) NSString *refusalCode;
@property(nonatomic, copy, readonly) NSString *refusalReason;
@property(nonatomic, copy, readonly) NSString *outcome;

- (instancetype)initWithCommandId:(NSString *)commandId
                        backendId:(NSString *)backendId
                         exitCode:(NSInteger)exitCode
                       stdoutText:(NSString *)stdoutText
                       stderrText:(NSString *)stderrText
                          refused:(BOOL)refused
                      refusalCode:(NSString *)refusalCode
                    refusalReason:(NSString *)refusalReason
                          outcome:(NSString *)outcome;

+ (instancetype)refusalWithCommandId:(NSString *)commandId
                            backendId:(NSString *)backendId
                         refusalCode:(NSString *)refusalCode
                       refusalReason:(NSString *)refusalReason;

- (NSString *)displayText;

@end

@interface FacManCommandClient : NSObject

+ (NSArray<FacManCommandDefinition *> *)catalog;
+ (FacManCommandDefinition *)definitionForCommandId:(NSString *)commandId;

- (void)executeCommandId:(NSString *)commandId
                  inputs:(NSDictionary<NSString *, NSString *> *)inputs
               workspace:(NSString *)workspace
                 cliPath:(NSString *)cliPath
              completion:(void (^)(FacManCommandResult *result))completion;

@end
