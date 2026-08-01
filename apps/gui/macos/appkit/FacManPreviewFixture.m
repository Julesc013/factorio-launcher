// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "FacManPreviewFixture.h"

@interface FacManPreviewFixture ()
@property(nonatomic, assign, readwrite) FacManPreviewState state;
@property(nonatomic, copy, readwrite) NSString *stateId;
@property(nonatomic, copy, readwrite) NSString *readiness;
@property(nonatomic, copy, readwrite) NSString *statusText;
@property(nonatomic, copy, readwrite) NSString *primaryLabel;
@property(nonatomic, copy, readwrite) NSString *primaryAccessibilityLabel;
@property(nonatomic, copy, readwrite) NSString *activitySummary;
@property(nonatomic, copy, readwrite) NSString *operationId;
@property(nonatomic, copy, readwrite) NSString *lastRun;
@property(nonatomic, copy, readwrite) NSString *recoveryId;
@property(nonatomic, copy, readwrite) NSString *refusalCode;
@property(nonatomic, assign, readwrite) BOOL primaryEnabled;
@end

@implementation FacManPreviewFixture

+ (instancetype)fixtureForState:(FacManPreviewState)state
{
    FacManPreviewFixture *fixture = [[self alloc] init];
    fixture.state = state;
    fixture.operationId = @"";
    fixture.lastRun = @"No previous run";
    fixture.recoveryId = @"";
    fixture.refusalCode = @"";
    fixture.primaryEnabled = YES;
    switch (state) {
        case FacManPreviewStateStaleReadiness:
            fixture.stateId = @"refused";
            fixture.readiness = @"Stale — observed revision 7; current revision 8";
            fixture.statusText = @"Play unavailable: readiness changed";
            fixture.primaryLabel = @"Play";
            fixture.primaryAccessibilityLabel = @"Play unavailable because readiness is stale";
            fixture.activitySummary = @"No process started. Play was refused before effects.";
            fixture.refusalCode = @"stale_readiness";
            break;
        case FacManPreviewStateRunning:
            fixture.stateId = @"running";
            fixture.readiness = @"Ready — revision 7";
            fixture.statusText = @"Running under backend supervision";
            fixture.primaryLabel = @"Show in Activity";
            fixture.primaryAccessibilityLabel = @"Show running operation in Activity";
            fixture.activitySummary = @"1 operation is running.";
            fixture.operationId = @"operation.fixture-play-001";
            break;
        case FacManPreviewStateExited:
            fixture.stateId = @"exited";
            fixture.readiness = @"Ready — revision 7";
            fixture.statusText = @"Last run exited normally; ready to relaunch";
            fixture.primaryLabel = @"Relaunch";
            fixture.primaryAccessibilityLabel = @"Relaunch deterministic fixture journey";
            fixture.activitySummary = @"Last fixture operation exited normally.";
            fixture.lastRun = @"Exited normally · code 0 · operation.fixture-play-001";
            break;
        case FacManPreviewStateInterrupted:
            fixture.stateId = @"interrupted";
            fixture.readiness = @"Ready — revision 7";
            fixture.statusText = @"Recovery required after interruption";
            fixture.primaryLabel = @"Inspect recovery";
            fixture.primaryAccessibilityLabel = @"Inspect interrupted operation recovery";
            fixture.activitySummary = @"1 interrupted operation requires recovery.";
            fixture.operationId = @"operation.fixture-play-001";
            fixture.lastRun = @"Interrupted · outcome unknown · operation.fixture-play-001";
            fixture.recoveryId = @"recovery.fixture-play-001";
            break;
        case FacManPreviewStateReady:
        default:
            fixture.stateId = @"positive";
            fixture.readiness = @"Ready — revision 7";
            fixture.statusText = @"Ready";
            fixture.primaryLabel = @"Play";
            fixture.primaryAccessibilityLabel = @"Play deterministic fixture journey";
            fixture.activitySummary = @"No active operations.";
            break;
    }
    return fixture;
}

@end
