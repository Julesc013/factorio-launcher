// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import <Foundation/Foundation.h>
#import "FacManPreviewFixture.h"

@class FacManCommandClient;

@interface FacManLivePresentation : NSObject

@property(nonatomic, assign, readonly) FacManPreviewState state;
@property(nonatomic, copy, readonly) NSString *stateId;
@property(nonatomic, copy, readonly) NSString *readiness;
@property(nonatomic, copy, readonly) NSString *statusText;
@property(nonatomic, copy, readonly) NSString *primaryLabel;
@property(nonatomic, copy, readonly) NSString *primaryAccessibilityLabel;
@property(nonatomic, copy, readonly) NSString *activitySummary;
@property(nonatomic, copy, readonly) NSString *operationId;
@property(nonatomic, copy, readonly) NSString *lastRun;
@property(nonatomic, copy, readonly) NSString *recoveryId;
@property(nonatomic, copy, readonly) NSString *refusalCode;
@property(nonatomic, copy, readonly) NSString *refusalDetail;
@property(nonatomic, copy, readonly) NSString *selectedInstanceId;
@property(nonatomic, copy, readonly) NSString *instanceSummary;
@property(nonatomic, copy, readonly) NSString *installationSummary;
@property(nonatomic, assign, readonly) BOOL primaryEnabled;
@property(nonatomic, assign, readonly) BOOL recoveryRequired;

- (instancetype)initWithCommandClient:(FacManCommandClient *)client;
- (void)refreshWithWorkspace:(NSString *)workspace
                     cliPath:(NSString *)cliPath
                  completion:(void (^)(void))completion;
- (void)playWithWorkspace:(NSString *)workspace
                  cliPath:(NSString *)cliPath
               completion:(void (^)(void))completion;
- (void)recoverWithWorkspace:(NSString *)workspace
                     cliPath:(NSString *)cliPath
                  completion:(void (^)(void))completion;

@end
