// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import <Foundation/Foundation.h>

typedef NS_ENUM(NSInteger, FacManPreviewState) {
    FacManPreviewStateReady = 0,
    FacManPreviewStateStaleReadiness = 1,
    FacManPreviewStateRunning = 2,
    FacManPreviewStateExited = 3,
    FacManPreviewStateInterrupted = 4
};

@interface FacManPreviewFixture : NSObject

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
@property(nonatomic, assign, readonly) BOOL primaryEnabled;

+ (instancetype)fixtureForState:(FacManPreviewState)state;

@end
