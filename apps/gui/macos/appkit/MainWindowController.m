// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "MainWindowController.h"
#import "CommandClient.h"

@interface MainWindowController ()
@property(nonatomic, strong) FacManCommandClient *commandClient;
@property(nonatomic, strong) NSTextField *cliPathField;
@property(nonatomic, strong) NSTextField *workspaceField;
@property(nonatomic, strong) NSTextView *resultView;
@property(nonatomic, strong) NSMutableDictionary<NSString *, NSTextField *> *inputFields;
@property(nonatomic, strong) NSPopUpButton *commandPopup;
@end

static NSString *FacManStatusText(FacManCommandStatus status);
static NSString *FacManVisualizationTitle(NSString *renderer);

@implementation MainWindowController

- (instancetype)init
{
    NSRect frame = NSMakeRect(0, 0, 1080, 720);
    NSWindow *window = [[NSWindow alloc] initWithContentRect:frame
                                                   styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable | NSWindowStyleMaskMiniaturizable)
                                                     backing:NSBackingStoreBuffered
                                                       defer:NO];
    [window setTitle:@"FacMan AppKit Shell"];
    self = [super initWithWindow:window];
    if (self) {
        _commandClient = [[FacManCommandClient alloc] init];
        _inputFields = [NSMutableDictionary dictionary];
        [self buildLayout];
        [self loadDefaults];
        [self renderText:@"Ready. Configure a facman executable if it is not bundled with this AppKit app."];
    }
    return self;
}

- (void)buildLayout
{
    NSView *content = [[NSView alloc] initWithFrame:[[self window] contentView].bounds];
    [content setAutoresizingMask:(NSViewWidthSizable | NSViewHeightSizable)];
    [[self window] setContentView:content];

    CGFloat width = NSWidth([content bounds]);
    CGFloat height = NSHeight([content bounds]);

    NSView *bar = [[NSView alloc] initWithFrame:NSMakeRect(0, height - 72, width, 72)];
    [bar setAutoresizingMask:(NSViewWidthSizable | NSViewMinYMargin)];
    [content addSubview:bar];
    [self addLabel:@"CLI path" toView:bar frame:NSMakeRect(12, 42, 72, 20)];
    self.cliPathField = [self addTextFieldToView:bar key:nil frame:NSMakeRect(88, 38, width - 360, 24) placeholder:@""];
    [self addButton:@"Status" commandId:@"workspace.status" toView:bar frame:NSMakeRect(width - 250, 36, 104, 28)];
    [self addButton:@"Product" commandId:@"product.inspect" toView:bar frame:NSMakeRect(width - 136, 36, 104, 28)];

    [self addLabel:@"Workspace" toView:bar frame:NSMakeRect(12, 12, 72, 20)];
    self.workspaceField = [self addTextFieldToView:bar key:nil frame:NSMakeRect(88, 8, width - 360, 24) placeholder:@""];
    [self addLabel:@"Transport: CLI JSON" toView:bar frame:NSMakeRect(width - 250, 10, 110, 20)];
    NSButton *cancel = [[NSButton alloc] initWithFrame:NSMakeRect(width - 132, 6, 100, 28)];
    [cancel setTitle:@"Cancel"];
    [cancel setTarget:self];
    [cancel setAction:@selector(cancelCommand:)];
    [bar addSubview:cancel];

    NSTabView *tabs = [[NSTabView alloc] initWithFrame:NSMakeRect(0, 220, width, height - 292)];
    [tabs setAutoresizingMask:(NSViewWidthSizable | NSViewHeightSizable)];
    [content addSubview:tabs];
    [self addDashboardTab:tabs];
    [self addDoctorTab:tabs];
    [self addInstallsTab:tabs];
    [self addInstancesTab:tabs];
    [self addGeneratedTab:@"Snapshots" prefixes:@[ @"snapshots." ] toTabs:tabs];
    [self addGeneratedTab:@"Profiles" prefixes:@[ @"profiles.", @"templates." ] toTabs:tabs];
    [self addLaunchPlanTab:tabs];
    [self addGeneratedTab:@"Mods" prefixes:@[ @"mods.", @"modsets." ] toTabs:tabs];
    [self addGeneratedTab:@"Saves" prefixes:@[ @"saves." ] toTabs:tabs];
    [self addGeneratedTab:@"Servers" prefixes:@[ @"servers." ] toTabs:tabs];
    [self addDiagnosticsTab:tabs];
    [self addGeneratedTab:@"Recovery" prefixes:@[ @"workspace.recovery.", @"workspace.migration." ] toTabs:tabs];
    [self addGeneratedTab:@"Capabilities" prefixes:@[ @"capabilities.", @"workspace." ] toTabs:tabs];
    [self addSettingsTab:tabs];

    NSScrollView *scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(0, 0, width, 220)];
    [scroll setAutoresizingMask:(NSViewWidthSizable | NSViewMaxYMargin)];
    [scroll setHasVerticalScroller:YES];
    [scroll setHasHorizontalScroller:YES];
    self.resultView = [[NSTextView alloc] initWithFrame:[[scroll contentView] bounds]];
    [self.resultView setEditable:NO];
    [self.resultView setFont:[NSFont userFixedPitchFontOfSize:12.0]];
    [scroll setDocumentView:self.resultView];
    [content addSubview:scroll];
}

- (void)addDashboardTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Dashboard" toTabs:tabs];
    [self addLabel:@"Shared command graph surface" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    NSTextView *catalog = [[NSTextView alloc] initWithFrame:NSMakeRect(16, 74, 1000, 284)];
    [catalog setEditable:NO];
    [catalog setFont:[NSFont userFixedPitchFontOfSize:11.0]];
    NSMutableString *text = [NSMutableString string];
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        [text appendFormat:@"%@ -> %@ [%@]\n", command.commandId, command.backendId, FacManStatusText(command.status)];
        if ([command.deferredReason length] > 0) {
            [text appendFormat:@"  %@\n", command.deferredReason];
        }
    }
    [catalog setString:text];
    [view addSubview:catalog];
    self.commandPopup = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(16, 28, 360, 28) pullsDown:NO];
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        [self.commandPopup addItemWithTitle:command.commandId];
        [[self.commandPopup lastItem] setRepresentedObject:command.commandId];
    }
    [view addSubview:self.commandPopup];
    NSButton *open = [[NSButton alloc] initWithFrame:NSMakeRect(388, 26, 142, 32)];
    [open setTitle:@"Open Command"];
    [open setTarget:self];
    [open setAction:@selector(runSelectedCommand:)];
    [view addSubview:open];
}

- (void)addDoctorTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Doctor" toTabs:tabs];
    [self addLabel:@"Workspace checks" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addButton:@"Run Doctor" commandId:@"doctor.run" toView:view frame:NSMakeRect(16, 320, 142, 32)];
    [self addButton:@"Inspect Product" commandId:@"product.inspect" toView:view frame:NSMakeRect(168, 320, 142, 32)];
    [self addButton:@"Explain Doctor" commandId:@"doctor.explain" toView:view frame:NSMakeRect(320, 320, 142, 32)];
}

- (void)addInstallsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Installs" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"install_refs.", @"installs.", @"setup." ]];
}

- (void)addInstancesTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Instances" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"instance." ]];
}

- (void)addLaunchPlanTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Launch Plan" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"launch_plan.", @"run." ]];
}

- (void)addDiagnosticsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Diagnostics" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"diagnostics.", @"dev." ]];
}

- (void)addGeneratedTab:(NSString *)title prefixes:(NSArray<NSString *> *)prefixes toTabs:(NSTabView *)tabs
{
    NSView *view = [self addTab:title toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:prefixes];
}

- (void)addGeneratedCommandsToView:(NSView *)view prefixes:(NSArray<NSString *> *)prefixes
{
    NSInteger index = 0;
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        BOOL included = NO;
        for (NSString *prefix in prefixes) if ([command.backendId hasPrefix:prefix]) included = YES;
        if (!included) continue;
        NSInteger column = index % 3;
        NSInteger row = index / 3;
        NSRect frame = NSMakeRect(16 + column * 320, 350 - row * 48, 300, 34);
        [self addButton:command.label commandId:command.commandId toView:view frame:frame];
        index++;
    }
}

- (void)addSettingsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Settings/About" toTabs:tabs];
    NSTextView *info = [[NSTextView alloc] initWithFrame:NSMakeRect(16, 130, 940, 250)];
    [info setEditable:NO];
    [info setString:
        @"FACMAN-APPKIT-SHELL-01\n\n"
        @"This app is a thin AppKit frontend over the shared FacMan command graph.\n"
        @"It renders required command results returned by the configured backend path "
        @"and keeps deferred commands disabled or refused with reasons.\n\n"
        @"It does not implement Factorio discovery logic, setup mutation, Mod Portal network access, "
        @"modset resolution, save/export/import behavior, server execution, developer execution, "
        @"credential storage, or direct Factorio launch behavior in Objective-C."];
    [view addSubview:info];
    [self addButton:@"Workspace Paths" commandId:@"workspace.paths" toView:view frame:NSMakeRect(16, 80, 132, 30)];
    [self addButton:@"Capabilities" commandId:@"capabilities.inspect" toView:view frame:NSMakeRect(158, 80, 132, 30)];
}

- (NSView *)addTab:(NSString *)title toTabs:(NSTabView *)tabs
{
    NSTabViewItem *item = [[NSTabViewItem alloc] initWithIdentifier:title];
    [item setLabel:title];
    NSView *view = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 1040, 420)];
    [item setView:view];
    [tabs addTabViewItem:item];
    return view;
}

- (NSTextField *)addTextFieldToView:(NSView *)view key:(NSString *)key frame:(NSRect)frame placeholder:(NSString *)placeholder
{
    NSTextField *field = [[NSTextField alloc] initWithFrame:frame];
    [field setStringValue:placeholder ?: @""];
    [field setAccessibilityLabel:key ?: @"Path or command input"];
    [view addSubview:field];
    if (key != nil) {
        [self.inputFields setObject:field forKey:key];
    }
    return field;
}

- (void)addLabel:(NSString *)text toView:(NSView *)view frame:(NSRect)frame
{
    NSTextField *label = [[NSTextField alloc] initWithFrame:frame];
    [label setStringValue:text];
    [label setEditable:NO];
    [label setBezeled:NO];
    [label setDrawsBackground:NO];
    [label setAccessibilityLabel:text];
    [view addSubview:label];
}

- (void)addButton:(NSString *)title commandId:(NSString *)commandId toView:(NSView *)view frame:(NSRect)frame
{
    NSButton *button = [[NSButton alloc] initWithFrame:frame];
    [button setTitle:title];
    [button setButtonType:NSButtonTypeMomentaryPushIn];
    [button setBezelStyle:NSBezelStyleRounded];
    [button setTarget:self];
    [button setAction:@selector(runCommand:)];
    [button setIdentifier:commandId];
    [button setAccessibilityLabel:title];
    [button setAccessibilityHelp:[NSString stringWithFormat:@"Run generated command %@", commandId]];
    [view addSubview:button];
}

- (void)addDeferredButton:(NSString *)commandId toView:(NSView *)view frame:(NSRect)frame
{
    FacManCommandDefinition *command = [FacManCommandClient definitionForCommandId:commandId];
    NSButton *button = [[NSButton alloc] initWithFrame:frame];
    [button setTitle:commandId];
    [button setEnabled:NO];
    [button setToolTip:command.deferredReason];
    [view addSubview:button];
}

- (void)runCommand:(id)sender
{
    NSString *commandId = [sender identifier];
    [self runCommandId:commandId sender:sender];
}

- (void)runSelectedCommand:(id)sender
{
    (void)sender;
    NSString *commandId = [[self.commandPopup selectedItem] representedObject];
    [self runCommandId:commandId sender:nil];
}

- (void)cancelCommand:(id)sender
{
    (void)sender;
    [self.commandClient cancelCurrentCommand];
    [self renderText:@"Cancellation requested."];
}

- (void)runCommandId:(NSString *)commandId sender:(id)sender
{
    FacManCommandDefinition *command = [FacManCommandClient definitionForCommandId:commandId];
    BOOL cancelled = NO;
    NSDictionary<NSString *, NSString *> *inputs = [self generatedInputsForCommand:command cancelled:&cancelled];
    if (cancelled) return;
    [self renderText:[NSString stringWithFormat:@"Running %@...", commandId]];
    if (sender != nil) [sender setEnabled:NO];
    [self.commandClient executeCommandId:commandId
                                  inputs:inputs
                               workspace:[self.workspaceField stringValue]
                                 cliPath:[self.cliPathField stringValue]
                              completion:^(FacManCommandResult *result) {
                                  [self renderText:[NSString stringWithFormat:@"View: %@\nRisk: %@\nEffects: %@\n\n%@",
                                      FacManVisualizationTitle(command.renderer), command.riskTier, command.effects,
                                      [result displayText]]];
                                  if (sender != nil) [sender setEnabled:YES];
                              }];
}

- (NSDictionary<NSString *, NSString *> *)generatedInputsForCommand:(FacManCommandDefinition *)command
                                                         cancelled:(BOOL *)cancelled
{
    if (cancelled != NULL) *cancelled = NO;
    if (command == nil || command.status != FacManCommandStatusImplemented) return @{};
    NSData *data = [command.inputDefinitions dataUsingEncoding:NSUTF8StringEncoding];
    NSArray<NSDictionary *> *fields = data == nil ? @[] : [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if ([fields count] == 0) return @{};
    NSAlert *alert = [[NSAlert alloc] init];
    [alert setMessageText:command.label];
    [alert setInformativeText:[NSString stringWithFormat:@"Availability: %@ | Risk: %@ | Effects: %@",
        command.availability, command.riskTier, command.effects]];
    [alert addButtonWithTitle:(command.dryRunDefault ? @"Run" : @"Apply")];
    [alert addButtonWithTitle:@"Cancel"];
    CGFloat height = MAX(60.0, [fields count] * 42.0);
    NSView *form = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 520, height)];
    NSMutableDictionary<NSString *, NSControl *> *controls = [NSMutableDictionary dictionary];
    NSInteger index = 0;
    for (NSDictionary *field in fields) {
        NSString *key = [field objectForKey:@"key"];
        BOOL required = [[field objectForKey:@"required"] boolValue];
        CGFloat y = height - 34 - index * 42;
        [self addLabel:[key stringByAppendingString:(required ? @" *" : @"")]
                 toView:form
                  frame:NSMakeRect(0, y + 2, 150, 22)];
        NSString *type = [field objectForKey:@"type"];
        NSControl *control = nil;
        NSArray *choices = [field objectForKey:@"choices"];
        if ([choices count] > 0) {
            NSPopUpButton *popup = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(160, y, 350, 26) pullsDown:NO];
            if (!required) [popup addItemWithTitle:@""];
            [popup addItemsWithTitles:choices];
            control = popup;
        } else if ([type isEqualToString:@"boolean"]) {
            NSButton *toggle = [[NSButton alloc] initWithFrame:NSMakeRect(160, y, 330, 24)];
            [toggle setButtonType:NSSwitchButton];
            [toggle setTitle:@"Enabled"];
            control = toggle;
        } else if ([type isEqualToString:@"path"]) {
            NSPathControl *path = [[NSPathControl alloc] initWithFrame:NSMakeRect(160, y, 350, 26)];
            [path setPathStyle:NSPathStyleStandard];
            control = path;
        } else {
            NSTextField *text = [[NSTextField alloc] initWithFrame:NSMakeRect(160, y, 350, 24)];
            NSString *defaultValue = [field objectForKey:@"default"];
            if ([defaultValue isKindOfClass:[NSString class]]) [text setStringValue:defaultValue];
            control = text;
        }
        [form addSubview:control];
        [control setAccessibilityLabel:key];
        [control setAccessibilityHelp:[NSString stringWithFormat:@"%@ %@ field", required ? @"Required" : @"Optional", type]];
        [controls setObject:control forKey:key];
        index++;
    }
    [alert setAccessoryView:form];
    if ([alert runModal] != NSAlertFirstButtonReturn) {
        if (cancelled != NULL) *cancelled = YES;
        return @{};
    }
    NSMutableDictionary<NSString *, NSString *> *inputs = [NSMutableDictionary dictionary];
    for (NSDictionary *field in fields) {
        NSString *key = [field objectForKey:@"key"];
        NSControl *control = [controls objectForKey:key];
        NSString *value = @"";
        if ([control isKindOfClass:[NSPathControl class]]) {
            value = [[(NSPathControl *)control URL] path] ?: @"";
        } else if ([control isKindOfClass:[NSButton class]]) {
            value = [(NSButton *)control state] == NSControlStateValueOn ? @"true" : @"false";
        } else if ([control isKindOfClass:[NSPopUpButton class]]) {
            value = [(NSPopUpButton *)control titleOfSelectedItem] ?: @"";
        } else if ([control isKindOfClass:[NSTextField class]]) {
            value = [(NSTextField *)control stringValue];
        }
        [inputs setObject:value forKey:key];
    }
    return inputs;
}

- (void)loadDefaults
{
    NSString *cli = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_CLI"];
    if ([cli length] > 0) {
        [self.cliPathField setStringValue:cli];
    }
    [self.workspaceField setStringValue:@""];
}

- (void)renderText:(NSString *)text
{
    [self.resultView setString:text ?: @""];
    NSAccessibilityPostNotification(self.resultView, NSAccessibilityValueChangedNotification);
}

@end

static NSString *FacManStatusText(FacManCommandStatus status)
{
    if (status == FacManCommandStatusImplemented) {
        return @"implemented";
    }
    if (status == FacManCommandStatusStubbedWithRefusal) {
        return @"stubbed_with_refusal";
    }
    return @"not_supported_with_reason";
}

static NSString *FacManVisualizationTitle(NSString *renderer)
{
    if ([renderer hasPrefix:@"instance_diff"]) return @"Instance diff";
    if ([renderer hasPrefix:@"snapshots_"]) return @"Snapshot list or diff";
    if ([renderer hasPrefix:@"modsets_"]) return @"Modset plan graph";
    if ([renderer hasPrefix:@"saves_"]) return @"Save index or retention plan";
    if ([renderer hasPrefix:@"servers_"]) return @"Server plan";
    if ([renderer containsString:@"recovery"] || [renderer containsString:@"transaction"])
        return @"Transaction and recovery state";
    return @"Structured command result";
}
